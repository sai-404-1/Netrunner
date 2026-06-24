"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { apiGetClient, apiPostClient } from "@/lib/api-client";
import { useToast } from "@/components/Toast";
import { OutputModal } from "@/components/Modal";
import { X, Maximize2 } from "lucide-react";

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
}

interface SelectOption {
  value: string;
  label: string;
}

interface Placeholder {
  name: string;
  label: string;
  default: string;
  type: string;
  options: SelectOption[];
}

function parsePlaceholders(schema_json?: string): Placeholder[] {
  if (!schema_json) return [];
  try {
    const schema = JSON.parse(schema_json);
    return (schema.placeholders || []).map(([name, label, def, type, options]: any) => ({
      name,
      label,
      default: String(def ?? ""),
      type: type || "text",
      options: (options || []).map((o: any) =>
        Array.isArray(o) ? { value: String(o[0]), label: String(o[1]) } : { value: String(o), label: String(o) }
      ),
    }));
  } catch {
    return [];
  }
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
  const [targetType, setTargetType] = useState<"host" | "group">("host");
  const [targetId, setTargetId] = useState(preselectedHost);
  const [dynArgs, setDynArgs] = useState<Record<string, string>>({});
  const [run, setRun] = useState<TaskRun | null>(null);
  const [polling, setPolling] = useState(false);
  const [outputModal, setOutputModal] = useState(false);
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
    if (!targetId) {
      const targets = targetType === "host" ? h || [] : g || [];
      if (targets.length) setTargetId(String(targets[0].id));
    }
  }

  useEffect(() => { load(); }, []);

  useEffect(() => {
    const targets = targetType === "host" ? hosts : groups;
    if (targets.length && !targetId) setTargetId(String(targets[0].id));
  }, [targetType, hosts, groups]);

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

  async function startRun(e: React.FormEvent) {
    e.preventDefault();
    try {
      const result = await apiPostClient("/api/run", {
        module_slug: moduleSlug,
        target_type: targetType,
        target_id: Number(targetId),
        args: dynArgs,
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
        <form onSubmit={startRun} className="space-y-4">
          <div className="grid lg:grid-cols-4 gap-4 items-end">
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
              Тип цели
              <select className="input" value={targetType} onChange={(e) => setTargetType(e.target.value as any)}>
                <option value="host">Хост</option>
                <option value="group">Группа</option>
              </select>
            </label>
            <label className="label">
              Цель
              <select className="input" value={targetId} onChange={(e) => setTargetId(e.target.value)}>
                {(targetType === "host" ? hosts : groups).map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name} #{t.id}
                  </option>
                ))}
              </select>
            </label>
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
        <pre className="bg-slate-950 text-gray-200 rounded-[10px] p-4 text-sm min-h-[260px] h-[calc(100vh-420px)] overflow-auto">
          {run
            ? output || `Задача #${run.id} завершена со статусом ${run.status}`
            : "Здесь появится stdout/stderr последней задачи."}
        </pre>
        {perHost.length > 0 && (
          <div className="mt-4 space-y-3">
            <h4 className="font-semibold">По хостам</h4>
            {perHost.map((item: any, i: number) => (
              <div key={i} className="border border-gray-200 rounded-lg overflow-hidden">
                <div className="flex justify-between gap-3 px-3 py-2 bg-slate-50 text-sm border-b border-gray-200">
                  <strong>{item.name || item.address || item.host_id || "Хост"}</strong>
                  <span className="text-gray-500">
                    {item.address || ""}
                    {item.port ? `:${item.port}` : ""}
                  </span>
                </div>
                <pre className="p-3 text-sm bg-white text-slate-900">{item.output || "Нет вывода"}</pre>
              </div>
            ))}
          </div>
        )}
      </div>

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
