"use client";

import { useState } from "react";
import { apiGetClient, apiPostClient } from "@/lib/api-client";
import { RefreshCw, Download, GitBranch } from "lucide-react";

/** Раздел «Обновление» — проверка и применение обновлений кода через git. */
export function UpdatePanel() {
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
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <GitBranch size={18} className="text-gray-400" />
        <h3 className="font-semibold">Обновление</h3>
      </div>

      <div className="flex gap-3 flex-wrap">
        <button onClick={check} disabled={loading} className="btn-secondary">
          <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
          {loading ? "Проверка…" : "Проверить обновления"}
        </button>
        {status?.behind && status.behind > 0 && (
          <>
            <button onClick={doPull} disabled={loading} className="btn">
              <Download size={16} />
              {loading ? "Загрузка…" : `Применить (${status.behind})`}
            </button>
            <button onClick={loadDiff} className="btn-secondary">
              {showDiff ? "Скрыть diff" : "Изменения"}
            </button>
          </>
        )}
      </div>

      {status && !status.error && (
        <div className="space-y-2 text-sm">
          {status.has_upstream === false && (
            <p className="text-yellow-500">⚠ Удалённый репозиторий (upstream) не настроен</p>
          )}
          {status.behind === 0 && status.has_upstream && <p className="text-green-500">✅ Актуальная версия</p>}
          {status.behind && status.behind > 0 && (
            <>
              <p className="text-orange-500">
                📦 Отставание на <strong>{status.behind}</strong> коммит(ов)
              </p>
              {status.last_message && (
                <pre className="bg-slate-950 text-gray-200 p-3 rounded text-xs whitespace-pre-wrap max-h-32 overflow-auto">
                  {status.last_message}
                </pre>
              )}
              {status.diff_stats && (
                <pre className="bg-slate-950 text-gray-200 p-3 rounded text-xs whitespace-pre-wrap max-h-40 overflow-auto">
                  {status.diff_stats}
                </pre>
              )}
            </>
          )}
        </div>
      )}

      {status?.error && <p className="text-sm text-red-500">❌ {status.error}</p>}

      {showDiff && diff && (
        <div className="space-y-2">
          {diff.files && (
            <pre className="bg-slate-950 text-gray-200 p-3 rounded text-xs whitespace-pre-wrap max-h-40 overflow-auto">{diff.files}</pre>
          )}
          {diff.stat && (
            <pre className="bg-slate-950 text-gray-200 p-3 rounded text-xs whitespace-pre-wrap max-h-40 overflow-auto">{diff.stat}</pre>
          )}
          {diff.diff && (
            <details>
              <summary className="cursor-pointer text-sm text-blue-500">Полный diff</summary>
              <pre className="bg-slate-950 text-gray-200 p-3 rounded text-xs whitespace-pre-wrap max-h-96 overflow-auto mt-2">{diff.diff}</pre>
            </details>
          )}
        </div>
      )}

      {pullResult && (
        <div className="space-y-2">
          <pre className="bg-slate-950 text-gray-200 p-3 rounded text-xs whitespace-pre-wrap max-h-40 overflow-auto">{pullResult}</pre>
          <p className="text-xs text-gray-500">⚠ Для применения изменений может потребоваться перезапуск контейнера.</p>
        </div>
      )}
    </div>
  );
}
