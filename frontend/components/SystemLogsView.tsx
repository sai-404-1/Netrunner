"use client";

import { useEffect, useState } from "react";
import { apiGetClient } from "@/lib/api-client";
import { formatDate } from "@/lib/utils";
import { RefreshCw } from "lucide-react";

interface SystemLog {
  id: number;
  category: string;
  level: string;
  message: string;
  host_id?: number | null;
  created_at: string;
}

const CATEGORY_LABELS: Record<string, string> = {
  agent_install: "Установка агента",
};

function levelClass(level: string) {
  if (level === "error") return "badge badge-error";
  if (level === "success") return "badge badge-success";
  return "badge";
}

const LEVEL_LABELS: Record<string, string> = {
  error: "Ошибка",
  success: "Успешно",
  info: "Инфо",
};

/** Содержимое вкладки «Логи» (журнал внутренних процессов сервера — например,
 * попытки автоустановки endpoint-агента при добавлении хоста). Не путать с
 * «История» (запуски модулей пользователем). */
export function SystemLogsView() {
  const [logs, setLogs] = useState<SystemLog[]>([]);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const r = await apiGetClient("/api/system-logs?limit=200");
      setLogs(r || []);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="panel">
      <div className="flex justify-end mb-3">
        <button className="btn-secondary" onClick={load} disabled={loading}>
          <RefreshCw size={16} className={loading ? "animate-spin" : ""} /> Обновить
        </button>
      </div>
      <div className="overflow-auto border border-gray-200 dark:border-gray-700 rounded-2xl bg-white dark:bg-gray-800">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 dark:bg-gray-800 text-xs uppercase tracking-wider text-slate-700 dark:text-gray-300">
            <tr>
              <th className="px-4 py-3 text-left font-semibold border-b border-gray-200 dark:border-gray-700">Когда</th>
              <th className="px-4 py-3 text-left font-semibold border-b border-gray-200 dark:border-gray-700">Категория</th>
              <th className="px-4 py-3 text-left font-semibold border-b border-gray-200 dark:border-gray-700">Статус</th>
              <th className="px-4 py-3 text-left font-semibold border-b border-gray-200 dark:border-gray-700">Сообщение</th>
            </tr>
          </thead>
          <tbody>
            {logs.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-gray-500 dark:text-gray-400">
                  Пока нет записей
                </td>
              </tr>
            ) : (
              logs.map((l) => (
                <tr key={l.id} className="border-b border-gray-100 dark:border-gray-700 last:border-b-0 hover:bg-slate-50 dark:hover:bg-gray-700/50">
                  <td className="px-4 py-3 align-middle whitespace-nowrap text-gray-700 dark:text-gray-300">{formatDate(l.created_at)}</td>
                  <td className="px-4 py-3 align-middle text-gray-700 dark:text-gray-300">{CATEGORY_LABELS[l.category] || l.category}</td>
                  <td className="px-4 py-3 align-middle">
                    <span className={levelClass(l.level)}>{LEVEL_LABELS[l.level] || l.level}</span>
                  </td>
                  <td className="px-4 py-3 align-middle text-gray-700 dark:text-gray-300 max-w-xl truncate" title={l.message}>
                    {l.message}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
