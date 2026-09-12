"use client";

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { apiGetClient, apiPostClient } from "@/lib/api-client";
import { useToast } from "@/components/Toast";
import { Modal, OutputModal } from "@/components/Modal";
import { FileManager } from "@/components/FileManager";
import { X, Maximize2, Loader2 } from "lucide-react";
import { Placeholder, parsePlaceholders } from "@/lib/module-schema";

export default function RunPage() {
  return (
    <Suspense fallback={<div className="p-6">Загрузка...</div>}>
      <RunForm />
    </Suspense>
  );
}

interface Host {
  id: number;
  name: string;
}

interface Group {
  id: number;
  name: string;
}

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

function RunForm() {
  const showToast = useToast();
  const params = useSearchParams();
  const preselected = params.get("module") || "";
  const preselectedHost = params.get("host") || "";

  const [modules, setModules] = useState<Module[]>([]);
  const [hosts, setHosts] = useState<Host[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [moduleSlug, setModuleSlug] = useState(preselected);
  // Единая цель в формате "host:5" / "group:3" — тип цели выводится неявно,
  // отдельное поле «Тип цели» в UI не показывается (он перенесён в модалку подтверждения).
  const [targetKey, setTargetKey] = useState(preselectedHost ? `host:${preselectedHost}` : "");
  const [dynArgs, setDynArgs] = useState<Record<string, string>>({});
  const [selectedFileIds, setSelectedFileIds] = useState<number[]>([]);
  const [run, setRun] = useState<TaskRun | null>(null);
  const [polling, setPolling] = useState(false);
  const [outputModal, setOutputModal] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const pollTimer = useRef<NodeJS.Timeout | null>(null);

  async function load() {
    const [m, h, g] = await Promise.all([
      apiGetClient("/api/modules"),
      apiGetClient("/api/hosts"),
      apiGetClient("/api/groups"),
    ]);
    const runnable = (m || []).filter((x: Module) => x.supports_task_runner);
    setModules(runnable);
    setHosts(h || []);
    setGroups(g || []);
    if (!moduleSlug && runnable.length) setModuleSlug(runnable[0].slug);
    if (!targetKey) {
      if ((h || []).length) setTargetKey(`host:${h[0].id}`);
      else if ((g || []).length) setTargetKey(`group:${g[0].id}`);
    }
  }

  useEffect(() => { load(); }, []);

  useEffect(() => {
    if (!targetKey) {
      if (hosts.length) setTargetKey(`host:${hosts[0].id}`);
      else if (groups.length) setTargetKey(`group:${groups[0].id}`);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hosts, groups]);

  // Reset dynamic args to defaults when module changes
  useEffect(() => {
    const m = modules.find((mod) => mod.slug === moduleSlug);
    const placeholders = parsePlaceholders(m?.schema_json);
    const defaults: Record<string, string> = {};
    for (const p of placeholders) defaults[p.name] = p.default;
    setDynArgs(defaults);
  }, [moduleSlug, modules]);

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
    } catch (err: any) {
      showToast(err.message, "error");
      setPolling(false);
    }
  }

  // Разбор строки цели "host:5" / "group:3" → тип и id.
  function parseTargetKey() {
    const [t, id] = targetKey.split(":");
    return { targetType: (t as "host" | "group") || "host", targetId: Number(id) };
  }

  // Текстовое представление выбранной цели для модалки подтверждения.
  const targetLabel = useMemo(() => {
    const { targetType, targetId } = parseTargetKey();
    const list = targetType === "host" ? hosts : groups;
    const t = list.find((x) => x.id === targetId);
    return t ? t.name : targetKey || "цель не выбрана";
  }, [targetKey, hosts, groups]);

  // Кнопка «Запустить» открывает модалку подтверждения, а не шлёт сразу.
  function requestRun(e: React.FormEvent) {
    e.preventDefault();
    if (!targetKey) { showToast("Выберите цель", "error"); return; }
    const isFileModule = moduleSlug === "file_distribute";
    if (isFileModule && selectedFileIds.length === 0) {
      showToast("Выберите хотя бы один файл для рассылки", "error");
      return;
    }
    setConfirmOpen(true);
  }

  async function doRun() {
    setConfirmOpen(false);
    const { targetType, targetId } = parseTargetKey();
    const isFileModule = moduleSlug === "file_distribute";
    try {
      const args: Record<string, unknown> = { ...dynArgs };
      if (isFileModule) args.file_ids = selectedFileIds;
      const result = await apiPostClient("/api/run", {
        module_slug: moduleSlug,
        target_type: targetType,
        target_id: targetId,
        args,
      });
      setRun({ id: result.run_id, status: "pending" });
      setPolling(true);
      connectWs(result.run_id);
      pollStatus(result.run_id);
      showToast(`Задача #${result.run_id} запущена`);
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  async function cancelRun() {
    if (!run) return;
    try {
      const result = await apiPostClient(`/api/run/${run.id}/cancel`, {});
      if (result.cancelled) showToast("Задача отменена");
      else showToast("Задача уже не активна", "error");
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  useEffect(() => {
    return () => {
      wsRef.current?.close();
      if (pollTimer.current) clearTimeout(pollTimer.current);
    };
  }, []);

  const activeModule = modules.find((m) => m.slug === moduleSlug);
  const placeholders = parsePlaceholders(activeModule?.schema_json);

  const perHost = run?.per_host_json ? JSON.parse(run.per_host_json) : [];
  const output = [run?.stdout_text || "", run?.stderr_text ? `--- stderr ---\n${run.stderr_text}` : ""]
    .filter(Boolean)
    .join("\n\n");

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold">Запуск задачи</h2>
        <p className="text-gray-500">Выбор цели, модуля и выполнение действия</p>
      </div>

      <div className="panel">
        <h3 className="font-semibold mb-4">Запуск модуля</h3>
        <form onSubmit={requestRun} className="space-y-4">
          <div className="grid lg:grid-cols-[1fr_1fr_auto_auto] gap-4 items-end">
            <label className="label">
              Модуль
              <select className="input" value={moduleSlug} onChange={(e) => setModuleSlug(e.target.value)}>
                {modules.map((m) => (
                  <option key={m.slug} value={m.slug}>
                    {m.name} ({m.slug})
                  </option>
                ))}
              </select>
            </label>
            <label className="label">
              Цель
              <select className="input" value={targetKey} onChange={(e) => setTargetKey(e.target.value)}>
                <optgroup label="Хосты">
                  {hosts.map((t) => (
                    <option key={`host-${t.id}`} value={`host:${t.id}`}>
                      {t.name} #{t.id}
                    </option>
                  ))}
                </optgroup>
                <optgroup label="Группы (кабинеты)">
                  {groups.map((t) => (
                    <option key={`group-${t.id}`} value={`group:${t.id}`}>
                      {t.name} #{t.id}
                    </option>
                  ))}
                </optgroup>
              </select>
            </label>
            <button type="button" className="btn-secondary" onClick={() => setConfirmOpen(true)}>
              Выбрать
            </button>
            <div className="flex gap-3">
              <button className="btn" type="submit" disabled={polling}>
                Запустить
              </button>
              {run && (run.status === "running" || run.status === "pending") && (
                <button type="button" className="btn-danger" onClick={cancelRun}>
                  <X size={16} /> Отменить
                </button>
              )}
            </div>
          </div>

          {placeholders.length > 0 && (
            <div className="grid md:grid-cols-2 gap-4 pt-2 border-t border-gray-100">
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
                        <option key={o.value} value={o.value}>
                          {o.label}
                        </option>
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

          {moduleSlug === "file_distribute" && (
            <FileManager selectedIds={selectedFileIds} onSelectionChange={setSelectedFileIds} />
          )}
        </form>
      </div>

      <div className="panel">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold">Результат выполнения</h3>
          {run && (
            <button className="btn-secondary py-1.5 px-3 text-sm" onClick={() => setOutputModal(true)}>
              <Maximize2 size={16} /> Развернуть
            </button>
          )}
        </div>
        {run && (run.status === "running" || run.status === "pending") && (run.progress?.total ?? 0) > 0 && (
          <div className="mb-4">
            <div className="flex justify-between text-sm text-gray-500 mb-1">
              <span>Обработка хостов…</span>
              <span>
                {run.progress!.done} из {run.progress!.total}
              </span>
            </div>
            <div className="h-2.5 w-full bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-600 transition-all duration-300"
                style={{ width: `${Math.round((run.progress!.done / run.progress!.total) * 100)}%` }}
              />
            </div>
          </div>
        )}
        <pre className="bg-slate-950 text-gray-200 rounded-[10px] p-4 text-sm min-h-[260px] h-[calc(100vh-420px)] overflow-auto">
          {run
            ? output || `Задача #${run.id} завершена со статусом ${run.status}`
            : "Здесь появится stdout/stderr последней задачи."}
        </pre>
        {perHost.length > 0 && (
          <div className="mt-4 space-y-3">
            <h4 className="font-semibold">По хостам</h4>
            {perHost.map((item: any, i: number) => {
              const state: string | undefined = item.state;
              const chip =
                state === "running"
                  ? { t: "Выполняется", c: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300" }
                  : state === "queued"
                  ? { t: "В очереди", c: "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300" }
                  : state === "error"
                  ? { t: "Ошибка", c: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300" }
                  : { t: "Готово", c: "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300" };
              const finished = state === "ok" || state === "error" || (!state && item.output);
              return (
                <div key={i} className="border border-gray-200 rounded-lg overflow-hidden">
                  <div className="flex items-center justify-between gap-3 px-3 py-2 bg-slate-50 text-sm border-b border-gray-200">
                    <span className="flex items-center gap-2 min-w-0">
                      <strong className="truncate">{item.name || item.address || item.host_id || "Хост"}</strong>
                      <span className="text-gray-500 shrink-0">
                        {item.address || ""}
                        {item.port ? `:${item.port}` : ""}
                      </span>
                    </span>
                    <span className={`shrink-0 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ${chip.c}`}>
                      {state === "running" && <Loader2 size={12} className="animate-spin" />}
                      {chip.t}
                    </span>
                  </div>
                  {finished ? (
                    <pre className="p-3 text-sm bg-white text-slate-900">{item.output || "Нет вывода"}</pre>
                  ) : (
                    <div className="p-3 text-sm text-gray-500">{state === "running" ? "Выполняется…" : "В очереди"}</div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {confirmOpen && (
        <Modal title="Подтвердите запуск" onClose={() => setConfirmOpen(false)}>
          <div className="space-y-4">
            <p className="text-sm text-gray-700 dark:text-gray-300">
              Вы хотите применить модуль <strong>{activeModule?.name || moduleSlug}</strong> к цели{" "}
              <strong>{targetLabel}</strong>?
            </p>
            <p className="text-sm text-gray-500">
              Подтвердите выбор: запустить {targetLabel}?
            </p>
            <div className="flex gap-3 justify-end">
              <button type="button" className="btn-secondary" onClick={() => setConfirmOpen(false)}>
                Нет
              </button>
              <button type="button" className="btn" onClick={doRun}>
                Да, запустить
              </button>
            </div>
          </div>
        </Modal>
      )}

      {outputModal && run && (
        <OutputModal
          text={output || `Задача #${run.id} завершена со статусом ${run.status}`}
          title={`Результат запуска #${run.id}`}
          onClose={() => setOutputModal(false)}
        />
      )}
    </div>
  );
}
