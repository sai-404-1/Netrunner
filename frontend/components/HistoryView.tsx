"use client";

import { useCallback, useEffect, useState } from "react";
import { apiGetClient } from "@/lib/api-client";
import { formatDate } from "@/lib/utils";
import { StatusBadge } from "@/components/Badge";
import { Modal } from "@/components/Modal";
import { RefreshCw } from "lucide-react";

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
  const PAGE_SIZE = 50;
  const [entries, setEntries] = useState<HistoryEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
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
      const qs = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(page * PAGE_SIZE) });
      if (sources.length) qs.set("sources", sources.join(","));
      const r = (await apiGetClient(`/api/history?${qs.toString()}`)) as { items: HistoryEntry[]; total: number };
      setEntries(r.items || []);
      setTotal(r.total || 0);
    } finally {
      setLoading(false);
    }
  }, [active, page]);

  useEffect(() => {
    loadServices();
  }, [loadServices]);

  useEffect(() => {
    if (services.length) load();
  }, [active, services.length, load]);

  // При смене фильтра сбрасываем на первую страницу
  useEffect(() => {
    setPage(0);
  }, [active]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

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
      </tr>
    );
  }

  return (
    <div className="space-y-4">
      {/* Фильтр-кнопки по сервисам: как кнопка «Выбрать» во вкладке хостов —
          активная синяя (btn), неактивная серая (btn-secondary) */}
      <div className="flex flex-wrap items-center gap-2">
        {services.map((s) => {
          const on = active.has(s.slug);
          return (
            <button
              key={s.slug}
              type="button"
              onClick={() => toggle(s.slug)}
              className={on ? "btn py-1.5 px-3 text-sm" : "btn-secondary py-1.5 px-3 text-sm"}
              title={s.name}
            >
              {s.name}
            </button>
          );
        })}
        <button
          type="button"
          className="btn-secondary py-1.5 px-3 text-sm ml-auto"
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
            </tr>
          </thead>
          <tbody>
            {entries.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray-500 dark:text-gray-400">
                  Нет записей истории.
                </td>
              </tr>
            ) : (
              entries.map(renderRow)
            )}
          </tbody>
        </table>
      </div>

      {/* Пагинация: Назад / счётчик / Вперёд */}
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm text-gray-500">
          Показано {entries.length ? page * PAGE_SIZE + 1 : 0}–{Math.min((page + 1) * PAGE_SIZE, total)} из {total}
        </span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="btn-secondary py-1.5 px-3 text-sm"
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0 || loading}
          >
            Назад
          </button>
          <span className="text-sm text-gray-500">
            стр. {page + 1} / {totalPages}
          </span>
          <button
            type="button"
            className="btn-secondary py-1.5 px-3 text-sm"
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1 || loading}
          >
            Вперёд
          </button>
        </div>
      </div>

      {/* Ленивая модалка подробностей конкретного ивента (по клику на строку) */}
      {detail && (
        <Modal
          title={detail.title}
          onClose={() => setDetail(null)}
          size="lg"
        >
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <span className="badge">{detail.source_name}</span>
              <StatusBadge status={detail.level} />
              <span className="text-sm text-gray-500 ml-auto">{formatDate(detail.created_at)}</span>
            </div>

            {detail.description && (
              <p className="text-sm text-gray-700 dark:text-gray-300">{detail.description}</p>
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
              <p className="text-sm text-gray-500">
                Инициатор: <span className="font-medium">{detail.actor_name}</span>
              </p>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
}
