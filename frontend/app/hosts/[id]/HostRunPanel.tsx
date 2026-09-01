"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Play, Loader2 } from "lucide-react";
import { apiGetClient, apiPostClient } from "@/lib/api-client";
import { useToast } from "@/components/Toast";
import { StatusBadge } from "@/components/Badge";
import { defaultArgs, parsePlaceholders } from "@/lib/module-schema";
import type { ProfileModule } from "@/lib/host-types";

interface RunState {
  id: number;
  status: string;
  stdout_text?: string;
  stderr_text?: string;
  progress?: { done: number; total: number };
}

/** Запуск модуля прямо на профиле машины — цель подставлена, выбирать хост не нужно.
 *  Список модулей приходит уже отфильтрованным по правам пользователя. */
export function HostRunPanel({ hostId, modules }: { hostId: number; modules: ProfileModule[] }) {
  const showToast = useToast();
  const [slug, setSlug] = useState("");
  const [args, setArgs] = useState<Record<string, string>>({});
  const [run, setRun] = useState<RunState | null>(null);
  const [starting, setStarting] = useState(false);
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const activeModule = useMemo(() => modules.find((m) => m.slug === slug), [modules, slug]);
  const placeholders = useMemo(() => parsePlaceholders(activeModule?.schema_json), [activeModule]);

  useEffect(() => {
    setArgs(defaultArgs(placeholders));
  }, [placeholders]);

  useEffect(() => () => {
    if (pollRef.current) clearTimeout(pollRef.current);
  }, []);

  function poll(runId: number) {
    apiGetClient(`/api/run/${runId}/status`)
      .then((data: RunState) => {
        setRun(data);
        if (data.status === "running" || data.status === "pending") {
          pollRef.current = setTimeout(() => poll(runId), 1500);
        }
      })
      .catch(() => {});
  }

  async function start() {
    if (!slug) {
      showToast("Выберите модуль", "error");
      return;
    }
    setStarting(true);
    setRun(null);
    if (pollRef.current) clearTimeout(pollRef.current);
    try {
      const result = await apiPostClient("/api/run", {
        module_slug: slug,
        target_type: "host",
        target_id: hostId,
        args,
      });
      poll(result.run_id);
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setStarting(false);
    }
  }

  if (modules.length === 0) {
    return <p className="text-sm text-gray-500">Доступных модулей нет.</p>;
  }

  const output = [run?.stdout_text, run?.stderr_text].filter(Boolean).join("\n").trim();

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-3">
        <label className="label flex-1 min-w-[16rem]">
          Модуль
          <select className="input" value={slug} onChange={(e) => setSlug(e.target.value)}>
            <option value="">Выберите модуль</option>
            {modules.map((m) => (
              <option key={m.id} value={m.slug}>{m.name}</option>
            ))}
          </select>
        </label>
        <button className="btn" onClick={start} disabled={starting || !slug}>
          {starting ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />} Запустить
        </button>
      </div>

      {activeModule?.description && (
        <p className="text-sm text-gray-500">{activeModule.description}</p>
      )}

      {placeholders.length > 0 && (
        <div className="grid md:grid-cols-2 gap-3 pt-2 border-t dark:border-gray-700">
          {placeholders.map((p) => (
            <label key={p.name} className={`label${p.type === "textarea" ? " md:col-span-2" : ""}`}>
              {p.label}
              {p.type === "textarea" ? (
                <textarea
                  className="input font-mono"
                  rows={3}
                  value={args[p.name] ?? p.default}
                  onChange={(e) => setArgs((prev) => ({ ...prev, [p.name]: e.target.value }))}
                />
              ) : p.type === "select" || p.type === "radio" ? (
                <select
                  className="input"
                  value={args[p.name] ?? p.default}
                  onChange={(e) => setArgs((prev) => ({ ...prev, [p.name]: e.target.value }))}
                >
                  {p.options.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              ) : (
                <input
                  className="input"
                  value={args[p.name] ?? p.default}
                  onChange={(e) => setArgs((prev) => ({ ...prev, [p.name]: e.target.value }))}
                  placeholder={p.default}
                />
              )}
            </label>
          ))}
        </div>
      )}

      {run && (
        <div className="rounded-[10px] border dark:border-gray-700">
          <div className="flex items-center justify-between gap-3 px-3 py-2">
            <span className="text-sm text-gray-500">Запуск #{run.id}</span>
            <StatusBadge status={run.status} />
          </div>
          {output && (
            <pre className="px-3 pb-3 text-xs bg-gray-50 dark:bg-gray-900 overflow-auto font-mono whitespace-pre-wrap max-h-64">
              {output}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
