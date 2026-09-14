"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { apiGetClient, apiPostClient } from "@/lib/api-client";
import { useToast } from "@/components/Toast";
import { OutputModal } from "@/components/Modal";
import { ChevronDown, Loader2 } from "lucide-react";
import { Placeholder, parsePlaceholders } from "@/lib/module-schema";
import type { Group, Host } from "@/lib/host-types";

interface Module {
  id: number;
  name: string;
  slug: string;
  supports_task_runner?: boolean;
  schema_json?: string;
}

interface TaskRun {
  id: number;
  status: string;
  stdout_text?: string;
  stderr_text?: string;
  per_host_json?: string;
  progress?: { done: number; total: number };
}

interface Props {
  hosts: Host[];
  groups: Group[];
}

export function RunPanel({ hosts, groups }: Props) {
  const showToast = useToast();
  const [modules, setModules] = useState<Module[]>([]);
  const [moduleSlug, setModuleSlug] = useState("");
  const [dynArgs, setDynArgs] = useState<Record<string, string>>({});
  const [polling, setPolling] = useState(false);
  const [resultOpen, setResultOpen] = useState(false);
  const [run, setRun] = useState<TaskRun | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Мультивыбор целей — кабинеты и хосты независимо.
  const [runGroupIds, setRunGroupIds] = useState<Set<number>>(new Set());
  const [runHostIds, setRunHostIds] = useState<Set<number>>(new Set());
  const [targetsOpen, setTargetsOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    (async () => {
      try {
        const m = await apiGetClient("/api/modules");
        const runnable = (m || []).filter((x: Module) => x.supports_task_runner);
        setModules(runnable);
        if (runnable.length) setModuleSlug((prev) => prev || runnable[0].slug);
      } catch (err: any) {
        showToast(err.message, "error");
      }
    })();
    return () => {
      wsRef.current?.close();
      if (pollTimer.current) clearTimeout(pollTimer.current);
    };
  }, [showToast]);

  // Значения полей модуля сбрасываются на дефолты при смене модуля.
  useEffect(() => {
    const m = modules.find((mod) => mod.slug === moduleSlug);
    const placeholders = parsePlaceholders(m?.schema_json);
    const defaults: Record<string, string> = {};
    for (const p of placeholders) defaults[p.name] = p.default;
    setDynArgs(defaults);
  }, [moduleSlug, modules]);

  // Клик вне раскрытой панели закрывает её.
  useEffect(() => {
    if (!targetsOpen) return;
    function handleClick(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setTargetsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [targetsOpen]);

  const activeModule = modules.find((m) => m.slug === moduleSlug);
  const placeholders: Placeholder[] = parsePlaceholders(activeModule?.schema_json);

  // Итоговое число уникальных хостов для отображения.
  const distinctHostCount = useMemo(() => {
    const ids = new Set<number>(runHostIds);
    for (const gid of runGroupIds) {
      const g = groups.find((gr) => gr.id === gid);
      if (g) g.hosts.forEach((h) => ids.add(typeof h === "number" ? h : h.id));
    }
    return ids.size;
  }, [runHostIds, runGroupIds, groups]);

  const targetSummary = useMemo(() => {
    const parts: string[] = [];
    if (runGroupIds.size) parts.push(`${runGroupIds.size} кабин.`);
    if (runHostIds.size) parts.push(`${runHostIds.size} хостов`);
    if (!parts.length) return "";
    return parts.join(", ") + (distinctHostCount > 0 ? ` · ${distinctHostCount} машин` : "");
  }, [runGroupIds.size, runHostIds.size, distinctHostCount]);

  function toggleGroup(id: number) {
    setRunGroupIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleHost(id: number) {
    setRunHostIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function connectWs(runId: number) {
    const wsUrl = `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}/api/python/ws`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;
    ws.onopen = () => ws.send(JSON.stringify({ action: "subscribe", run_id: runId }));
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "task_status" && data.run) {
          setRun(data.run);
          if (data.run.status !== "running" && data.run.status !== "pending") ws.close();
        }
      } catch {}
    };
    ws.onclose = () => { wsRef.current = null; };
  }

  async function pollStatus(runId: number) {
    try {
      const r = await apiGetClient(`/api/run/${runId}/status`);
      setRun(r);
      if (r.status === "running" || r.status === "pending") {
        pollTimer.current = setTimeout(() => pollStatus(runId), 1000);
      } else {
        setPolling(false);
      }
    } catch {
      setPolling(false);
    }
  }

  async function startRun() {
    if (!moduleSlug) {
      showToast("Выберите модуль", "error");
      return;
    }
    if (runGroupIds.size === 0 && runHostIds.size === 0) {
      showToast("Выберите хотя бы одну цель", "error");
      return;
    }
    try {
      const result = await apiPostClient("/api/run", {
        module_slug: moduleSlug,
        host_ids: [...runHostIds],
        group_ids: [...runGroupIds],
        args: { ...dynArgs },
      });
      setRun({ id: result.run_id, status: "pending" });
      setPolling(true);
      setResultOpen(true);
      connectWs(result.run_id);
      pollStatus(result.run_id);
      showToast(`Задача #${result.run_id} запущена`);
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  const output = [run?.stdout_text || "", run?.stderr_text ? `--- stderr ---\n${run.stderr_text}` : ""]
    .filter(Boolean)
    .join("\n\n");

  return (
    <div className="panel" ref={panelRef}>
      {/* Один ряд: Модуль · Цели ▾ · Запустить */}
      <div className="flex flex-wrap items-end gap-3">
        <label className="label flex-1 min-w-[14rem]">
          Модуль
          <select className="input appearance-none" value={moduleSlug} onChange={(e) => setModuleSlug(e.target.value)}>
            {modules.map((m) => (
              <option key={m.slug} value={m.slug}>{m.name} ({m.slug})</option>
            ))}
          </select>
        </label>

        <div className="label flex-1 min-w-[16rem]">
          Цели
          <button
            type="button"
            className="input flex items-center justify-between gap-2 cursor-pointer"
            onClick={() => setTargetsOpen((v) => !v)}
          >
            <span className={targetSummary ? "" : "text-gray-400"}>
              {targetSummary || "Выберите хосты или кабинеты…"}
            </span>
            <ChevronDown
              size={16}
              className={`shrink-0 text-gray-400 transition-transform ${targetsOpen ? "rotate-180" : ""}`}
            />
          </button>
        </div>

        <button
          className="btn shrink-0 self-end"
          type="button"
          onClick={startRun}
          disabled={polling}
        >
          {polling ? <Loader2 size={16} className="animate-spin" /> : null}
          Запустить
        </button>
      </div>

      {/* Раскрывающийся список целей */}
      {targetsOpen && (
        <div className="grid md:grid-cols-2 gap-4 rounded-[10px] border border-gray-200 dark:border-gray-700 p-3 mt-3 max-h-72 overflow-auto">
          {/* Колонка кабинетов */}
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-2">Кабинеты</div>
            {groups.length === 0 ? (
              <div className="text-sm text-gray-400">Нет кабинетов</div>
            ) : (
              <div className="flex flex-col gap-1">
                {groups.map((g) => (
                  <label key={g.id} className="flex items-center gap-2 cursor-pointer py-1 rounded hover:bg-gray-50 dark:hover:bg-gray-800 px-1">
                    <input
                      type="checkbox"
                      className="accent-blue-600"
                      checked={runGroupIds.has(g.id)}
                      onChange={() => toggleGroup(g.id)}
                    />
                    <span className="text-sm font-medium">{g.name}</span>
                    <span className="text-xs text-gray-400">({g.hosts.length})</span>
                  </label>
                ))}
              </div>
            )}
          </div>

          {/* Колонка хостов */}
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-2">Компьютеры</div>
            {hosts.length === 0 ? (
              <div className="text-sm text-gray-400">Нет хостов</div>
            ) : (
              <div className="flex flex-col gap-1">
                {hosts.map((h) => (
                  <label key={h.id} className="flex items-center gap-2 cursor-pointer py-1 rounded hover:bg-gray-50 dark:hover:bg-gray-800 px-1">
                    <input
                      type="checkbox"
                      className="accent-blue-600"
                      checked={runHostIds.has(h.id)}
                      onChange={() => toggleHost(h.id)}
                    />
                    <span className="text-sm font-medium truncate">{h.name}</span>
                    <span className="text-xs text-gray-400 font-mono shrink-0">{h.address}</span>
                  </label>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {placeholders.length > 0 && (
        <div className="grid md:grid-cols-2 gap-4 pt-4 mt-4 border-t border-gray-100 dark:border-gray-700">
          {placeholders.map((p) => (
            <label key={p.name} className={`label${p.type === "textarea" ? " md:col-span-2" : ""}`}>
              {p.label}
              {p.type === "textarea" ? (
                <textarea
                  className="input font-mono"
                  rows={3}
                  value={dynArgs[p.name] ?? p.default}
                  onChange={(e) => setDynArgs((prev) => ({ ...prev, [p.name]: e.target.value }))}
                  placeholder={p.default}
                />
              ) : p.type === "radio" ? (
                <div className="flex gap-4 flex-wrap mt-1">
                  {p.options.map((o) => (
                    <label key={o.value} className="flex items-center gap-1.5 cursor-pointer text-sm">
                      <input
                        type="radio"
                        name={p.name}
                        value={o.value}
                        checked={(dynArgs[p.name] ?? p.default) === o.value}
                        onChange={() => setDynArgs((prev) => ({ ...prev, [p.name]: o.value }))}
                        className="accent-blue-600"
                      />
                      {o.label}
                    </label>
                  ))}
                </div>
              ) : p.type === "select" ? (
                <select
                  className="input"
                  value={dynArgs[p.name] ?? p.default}
                  onChange={(e) => setDynArgs((prev) => ({ ...prev, [p.name]: e.target.value }))}
                >
                  {p.options.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              ) : (
                <input
                  className="input"
                  type={p.type === "password" ? "password" : "text"}
                  value={dynArgs[p.name] ?? p.default}
                  onChange={(e) => setDynArgs((prev) => ({ ...prev, [p.name]: e.target.value }))}
                  placeholder={p.default}
                />
              )}
            </label>
          ))}
        </div>
      )}

      {resultOpen && run && (
        <OutputModal
          text={output || `Задача #${run.id} — статус ${run.status}${run.progress ? ` (${run.progress.done}/${run.progress.total})` : ""}`}
          title={`Результат запуска #${run.id}`}
          onClose={() => setResultOpen(false)}
        />
      )}
    </div>
  );
}
