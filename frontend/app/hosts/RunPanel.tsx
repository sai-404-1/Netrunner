"use client";

// Блок запуска задачи, перенесённый на страницу «Хосты» (вкладка «Запуск задачи»
// убрана из сайдбара). Выбор цели — в списке хостов/кабинетов ниже: кнопка
// «Выбрать» включает режим выбора, клик по цели подсвечивает её (как выбор
// сценария на /scenarios). Тип цели определяется активной вкладкой (Хосты →
// хост, Кабинеты → кабинет), а не отдельным селектом.

import { useEffect, useRef, useState } from "react";
import { apiGetClient, apiPostClient } from "@/lib/api-client";
import { useToast } from "@/components/Toast";
import { OutputModal } from "@/components/Modal";
import { Loader2, X } from "lucide-react";
import { Placeholder, parsePlaceholders } from "@/lib/module-schema";

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
  /** Тип цели — следует за активной вкладкой страницы: Хосты → host, Кабинеты → group. */
  targetType: "host" | "group";
  /** Выбранная цель (id строкой) или "" если не выбрана. */
  targetId: string;
  /** Человекочитаемое имя выбранной цели. */
  targetName: string | null;
  /** Активен режим выбора цели (подсвечен список). */
  pickMode: boolean;
  /** Кнопка «Выбрать» — включить/выключить режим выбора цели. */
  onTogglePick: () => void;
  /** Сбросить выбранную цель. */
  onClearTarget: () => void;
}

export function RunPanel({
  targetType,
  targetId,
  targetName,
  pickMode,
  onTogglePick,
  onClearTarget,
}: Props) {
  const showToast = useToast();
  const [modules, setModules] = useState<Module[]>([]);
  const [moduleSlug, setModuleSlug] = useState("");
  const [dynArgs, setDynArgs] = useState<Record<string, string>>({});
  const [polling, setPolling] = useState(false);
  const [resultOpen, setResultOpen] = useState(false);
  const [run, setRun] = useState<TaskRun | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

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

  const activeModule = modules.find((m) => m.slug === moduleSlug);
  const placeholders: Placeholder[] = parsePlaceholders(activeModule?.schema_json);

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
    if (!targetId) {
      showToast("Выберите цель", "error");
      return;
    }
    try {
      const result = await apiPostClient("/api/run", {
        module_slug: moduleSlug,
        target_type: targetType,
        target_id: Number(targetId),
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
    <div className="panel">
      <div className="grid lg:grid-cols-4 gap-4 items-end">
        <label className="label">
          Модуль
          <select className="input" value={moduleSlug} onChange={(e) => setModuleSlug(e.target.value)}>
            {modules.map((m) => (
              <option key={m.slug} value={m.slug}>{m.name} ({m.slug})</option>
            ))}
          </select>
        </label>

        {/* Тип цели показан, но задаётся вкладкой (Хосты/Кабинеты), не выбором здесь. */}
        <div className="label">
          Тип цели
          <div className="input flex items-center text-gray-500">
            {targetType === "host" ? "Хост" : "Кабинет"}
          </div>
        </div>

        {/* Кнопка «Выбрать» — слева от поля цели (сначала выбираем, потом видим
            результат). В режиме выбора становится «Отмена». */}
        <div className="label">
          &nbsp;
          <button
            type="button"
            className={`btn w-full ${pickMode ? "bg-red-600 hover:bg-red-700" : ""}`}
            onClick={onTogglePick}
          >
            {pickMode ? "Отмена" : "Выбрать"}
          </button>
        </div>

        <div className="label">
          Цель
          <div className="input flex items-center gap-2 truncate">
            {targetName || <span className="text-gray-400">не выбрана</span>}
            {targetName && (
              <button type="button" className="text-gray-400 hover:text-red-500" onClick={onClearTarget} title="Сбросить цель">
                <X size={14} />
              </button>
            )}
          </div>
        </div>

        <div className="label">
          &nbsp;
          <button className="btn w-full" type="button" onClick={startRun} disabled={polling}>
            {polling ? <Loader2 size={16} className="animate-spin" /> : null}
            Запустить
          </button>
        </div>
      </div>

      {placeholders.length > 0 && (
        <div className="grid md:grid-cols-2 gap-4 pt-4 mt-4 border-t border-gray-100">
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
