"use client";

import { useCallback, useEffect, useState } from "react";
import { apiGetClient } from "@/lib/api-client";
import { formatDate } from "@/lib/utils";
import { StatusBadge } from "@/components/Badge";
import { RefreshCw, Eye } from "lucide-react";

interface HistoryColumn {
  key: string;
  label: string;
  value?: string | number | null;
}

interface HistoryEntry {
  id: number;
  source: string;
  source_name: string;
  event_type: string;
  event_label: string;
  actor_name?: string | null;
  title: string;
  description?: string | null;
  level: string;
  payload: Record<string, unknown>;
  columns: HistoryColumn[];
  created_at: string;
}

interface ServiceReg {
  slug: string;
  name: string;
  level: string;
  columns: { key: string; label: string }[];
  event_types: Record<string, { label: string; level: string }>;
}

/** Общая лента «История»: все сервисные события NetRunner в одной таблице.
 *  Колонки и фильтр-кнопки строятся динамически из реестра сервисов (API
 *  /api/history/types) — новый сервис появляется на фронте без пересборки. */
export function HistoryView() {
  const [entries, setEntries] = useState<HistoryEntry[]>([]);
  const [services, setServices] = useState<ServiceReg[]>([]);
  const [active, setActive] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [detail, setDetail] = useState<HistoryEntry | null>(null);

  const loadServices = useCallback(async () => {
    const r = (await apiGetClient("/api/history/types")) as ServiceReg[];
    setServices(r || []);
    setActive(new Set((r || []).map((s) => s.slug)));
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const sources = Array.from(active);
      const qs = sources.length ? `?limit=300&sources=${sources.join(",")}` : "?limit=300";
      const r = (await apiGetClient(`/api/history${qs}`)) as HistoryEntry[];
      setEntries(r || []);
    } finally {
      setLoading(false);
    }
  }, [active]);

  useEffect(() => {
    loadServices();
  }, [loadServices]);

  useEffect(() => {
    if (services.length) load();
  }, [active, services.length, load]);

  function toggle(slug: string) {
    setActive((prev) => {
      const next = new Set(prev);
      if (next.has(slug)) next.delete(slug);
      else next.add(slug);
      return next;
    });
  }

  // Динамические колонки: берём те, что есть в payload каждой записи, из реестра
  // сервиса (columns). Колонки могут отличаться между сервисами — рендерим по
  // данным конкретной записи.
  function renderRow(r: HistoryEntry) {
    return (
      <tr
        key={r.id}
        onClick={() => setDetail(r)}
        className="cursor-pointer border-b border-gray-100 dark:border-gray-700 last:border-b-0 hover:bg-slate-50 dark:hover:bg-gray-700/50"
      >
        <td className="px-4 py-3 whitespace-nowrap text-gray-500">{formatDate(r.created_at)}</td>
        <td className="px-4 py-3 whitespace-nowrap">
          <span className="badge">{r.source_name}</span>
        </td>
        <td className="px-4 py-3 font-medium text-gray-800 dark:text-gray-100">{r.title}</td>
        <td className="px-4 py-3 text-sm text-gray-500">{r.description || r.event_label || ""}</td>
        <td className="px-4 py-3 whitespace-nowrap text-gray-500">
          {r.actor_name || "—"}
        </td>
        <td className="px-4 py-3 whitespace-nowrap">
          <StatusBadge status={r.level} />
        </td>
        <td className="px-4 py-3 text-right">
          <Eye size={15} className="inline opacity-60" />
        </td>
      </tr>
    );
  }

  return (
    <div className="space-y-4">
      {/* Фильтр-кнопки по сервисам: клик включает/выключает (мульти-выбор) */}
      <div className="flex flex-wrap gap-2">
        {services.map((s) => {
          const on = active.has(s.slug);
          return (
            <button
              key={s.slug}
              type="button"
              onClick={() => toggle(s.slug)}
              className={`badge cursor-pointer transition-colors ${on ? "badge-success" : "opacity-50 hover:opacity-80"}`}
              title={s.name}
            >
              {s.name}
            </button>
          );
        })}
        <button
          type="button"
          className="btn-secondary ml-auto"
          onClick={load}
          disabled={loading}
          title="Обновить список"
        >
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Обновить
        </button>
      </div>

      <div className="overflow-auto border border-gray-200 dark:border-gray-700 rounded-2xl bg-white dark:bg-gray-800">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 dark:bg-gray-800 text-xs uppercase tracking-wider text-slate-700 dark:text-gray-300">
            <tr>
              <th className="px-4 py-3 text-left font-semibold border-b border-gray-200 dark:border-gray-700">Время</th>
              <th className="px-4 py-3 text-left font-semibold border-b border-gray-200 dark:border-gray-700">Сервис</th>
              <th className="px-4 py-3 text-left font-semibold border-b border-gray-200 dark:border-gray-700">Событие</th>
              <th className="px-4 py-3 text-left font-semibold border-b border-gray-200 dark:border-gray-700">Описание</th>
              <th className="px-4 py-3 text-left font-semibold border-b border-gray-200 dark:border-gray-700">Инициатор</th>
              <th className="px-4 py-3 text-left font-semibold border-b border-gray-200 dark:border-gray-700">Статус</th>
              <th className="px-4 py-3 border-b border-gray-200 dark:border-gray-700"></th>
            </tr>
          </thead>
          <tbody>
            {entries.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-gray-500 dark:text-gray-400">
                  Нет записей истории.
                </td>
              </tr>
            ) : (
              entries.map(renderRow)
            )}
          </tbody>
        </table>
      </div>

      {/* Ленивая модалка подробностей конкретного ивента (по клику на строку) */}
      {detail && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={() => setDetail(null)}
        >
          <div
            className="panel w-full max-w-2xl max-h-[80vh] overflow-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between mb-3">
              <div>
                <div className="flex items-center gap-2">
                  <span className="badge">{detail.source_name}</span>
                  <StatusBadge status={detail.level} />
                </div>
                <h3 className="text-lg font-bold mt-2">{detail.title}</h3>
                <p className="text-sm text-gray-500">{formatDate(detail.created_at)}</p>
              </div>
              <button className="btn-secondary" onClick={() => setDetail(null)}>Закрыть</button>
            </div>

            {detail.description && (
              <p className="text-sm text-gray-700 dark:text-gray-300 mb-4">{detail.description}</p>
            )}

            {detail.columns.filter((c) => c.value !== undefined && c.value !== null).length > 0 && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm">
                {detail.columns
                  .filter((c) => c.value !== undefined && c.value !== null)
                  .map((c) => (
                    <div key={c.key} className="flex justify-between gap-3 border-b border-gray-100 dark:border-gray-700 py-1">
                      <span className="text-gray-500">{c.label}</span>
                      <span className="font-medium text-right">{String(c.value)}</span>
                    </div>
                  ))}
              </div>
            )}

            {detail.actor_name && (
              <p className="text-sm text-gray-500 mt-4">
                Инициатор: <span className="font-medium">{detail.actor_name}</span>
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
