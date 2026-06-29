"use client";

import { useEffect, useState } from "react";
import { apiGetClient, apiPostClient } from "@/lib/api-client";

export default function UpdatePage() {
  const [status, setStatus] = useState<{ behind?: number; message?: string; has_upstream?: boolean; error?: string; last_message?: string; diff_stats?: string } | null>(null);
  const [diff, setDiff] = useState<{ stat?: string; diff?: string; files?: string; error?: string } | null>(null);
  const [pullResult, setPullResult] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [showDiff, setShowDiff] = useState(false);

  async function check() {
    setLoading(true);
    setDiff(null);
    setPullResult(null);
    try {
      const data = await apiGetClient("/update/check");
      setStatus(data);
    } catch (e: any) {
      setStatus({ error: e.message });
    }
    setLoading(false);
  }

  async function loadDiff() {
    setShowDiff(!showDiff);
    if (diff || !showDiff) return;
    try {
      const data = await apiGetClient("/update/diff");
      setDiff(data);
    } catch (e: any) {
      setDiff({ error: e.message });
    }
  }

  async function doPull() {
    setLoading(true);
    setPullResult(null);
    try {
      const data = await apiPostClient("/update/pull", {});
      setPullResult(data.stdout || data.error || "Готово");
      if (data.returncode === 0) setStatus((s) => ({ ...s, behind: 0, message: "Обновлено!" }));
    } catch (e: any) {
      setPullResult("Ошибка: " + e.message);
    }
    setLoading(false);
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Обновление</h1>

      <div className="flex gap-4 flex-wrap">
        <button onClick={check} disabled={loading} className="btn-primary">
          {loading ? "⏳ Проверка..." : "Проверить обновления"}
        </button>
        {status?.behind && status.behind > 0 && (
          <>
            <button onClick={doPull} disabled={loading} className="btn-primary bg-green-600 hover:bg-green-700">
              {loading ? "⏳ Загрузка..." : `Применить (${status.behind} коммита)`}
            </button>
            <button onClick={loadDiff} className="btn-secondary">
              {showDiff ? "Скрыть diff" : "Посмотреть изменения"}
            </button>
          </>
        )}
      </div>

      {status && !status.error && (
        <div className="card p-4 space-y-2">
          {status.has_upstream === false && (
            <p className="text-yellow-400">⚠ Нет удалённого репозитория (upstream не настроен)</p>
          )}
          {status.behind === 0 && status.has_upstream && (
            <p className="text-green-400">✅ Актуальная версия</p>
          )}
          {status.behind && status.behind > 0 && (
            <>
              <p className="text-orange-400">📦 Отставание на <strong>{status.behind}</strong> коммитов</p>
              <div className="bg-gray-900 p-3 rounded text-xs font-mono whitespace-pre-wrap max-h-32 overflow-auto text-gray-300">
                {status.last_message}
              </div>
              {status.diff_stats && (
                <div className="bg-gray-900 p-3 rounded text-xs font-mono whitespace-pre-wrap max-h-40 overflow-auto text-gray-300">
                  {status.diff_stats}
                </div>
              )}
            </>
          )}
        </div>
      )}

      {status?.error && (
        <div className="card p-4 border-red-500 text-red-400">
          ❌ {status.error}
        </div>
      )}

      {showDiff && diff && (
        <div className="card p-4 space-y-2">
          <h2 className="font-semibold">Изменения файлов</h2>
          {diff.files && (
            <div className="bg-gray-900 p-3 rounded text-xs font-mono whitespace-pre-wrap max-h-40 overflow-auto text-gray-300">
              {diff.files}
            </div>
          )}
          {diff.stat && (
            <div className="bg-gray-900 p-3 rounded text-xs font-mono whitespace-pre-wrap max-h-40 overflow-auto text-gray-300">
              {diff.stat}
            </div>
          )}
          {diff.diff && (
            <details>
              <summary className="cursor-pointer text-sm text-blue-400">Полный diff</summary>
              <div className="bg-gray-900 p-3 rounded text-xs font-mono whitespace-pre-wrap max-h-96 overflow-auto text-gray-300 mt-2">
                {diff.diff}
              </div>
            </details>
          )}
        </div>
      )}

      {pullResult && (
        <div className="card p-4 space-y-2">
          <h2 className="font-semibold">Результат применения</h2>
          <div className="bg-gray-900 p-3 rounded text-xs font-mono whitespace-pre-wrap max-h-40 overflow-auto text-gray-300">
            {pullResult}
          </div>
          <p className="text-sm text-gray-400 mt-2">⚠ Для применения изменений может потребоваться перезапуск контейнера.</p>
        </div>
      )}
    </div>
  );
}
