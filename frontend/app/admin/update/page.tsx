"use client";

import { useState } from "react";
import { apiGetClient, apiPostClient } from "@/lib/api-client";
import { RefreshCw, ArrowDown, Eye, EyeOff, RotateCcw, CheckCircle, XCircle, AlertTriangle, Server } from "lucide-react";

interface CheckResult {
  behind?: number;
  has_upstream?: boolean;
  message?: string;
  error?: string;
  last_message?: string;
  diff_stats?: string;
  version?: string;
}

interface DiffResult {
  stat?: string;
  diff?: string;
  files?: string;
  error?: string;
}

export default function AdminUpdatePage() {
  const [status, setStatus] = useState<CheckResult | null>(null);
  const [diff, setDiff] = useState<DiffResult | null>(null);
  const [pullResult, setPullResult] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [showDiff, setShowDiff] = useState(false);
  const [history, setHistory] = useState<{ time: string; result: string }[]>([]);

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
    const next = !showDiff;
    setShowDiff(next);
    if (!next) return;
    if (diff) return;
    try {
      const data = await apiGetClient("/update/diff");
      setDiff(data);
    } catch (e: any) {
      setDiff({ error: e.message });
    }
  }

  async function doPull(rebuild: boolean) {
    setLoading(true);
    setPullResult(null);
    try {
      const data = await apiPostClient("/update/pull", { rebuild });
      const text = data.stdout || data.error || "Готово";
      setPullResult(text);
      setHistory((h) => [
        { time: new Date().toLocaleTimeString(), result: "✅ Успешно" },
        ...h.slice(0, 19),
      ]);
      if (data.returncode === 0)
        setStatus((s: any) => ({ ...s, behind: 0, message: "Обновлено!" }));
    } catch (e: any) {
      setPullResult("Ошибка: " + e.message);
      setHistory((h) => [
        { time: new Date().toLocaleTimeString(), result: "❌ " + e.message },
        ...h.slice(0, 19),
      ]);
    }
    setLoading(false);
  }

  const hasUpdates = status?.behind && status.behind > 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <RefreshCw className="text-blue-400" size={24} />
          <h2 className="text-xl font-bold">Обновление системы</h2>
        </div>
        <button onClick={check} disabled={loading} className="btn-primary flex items-center gap-2">
          <RotateCcw size={16} className={loading ? "animate-spin" : ""} />
          {loading ? "Проверка..." : "Проверить"}
        </button>
      </div>

      <p className="text-sm text-gray-400">
        Проверяет и применяет обновления кода из Git-репозитория.
        После обновления может потребоваться пересборка Docker-образа.
      </p>

      {/* Статус */}
      {!status && !loading && (
        <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-6 text-center text-gray-400">
          Нажми «Проверить», чтобы узнать статус обновлений
        </div>
      )}

      {status && !status.error && (
        <div className={`rounded-lg border p-4 ${
          hasUpdates
            ? "bg-orange-900/20 border-orange-700"
            : status.has_upstream === false
            ? "bg-yellow-900/20 border-yellow-700"
            : "bg-green-900/20 border-green-700"
        }`}>
          <div className="flex items-start gap-3">
            {hasUpdates ? <AlertTriangle size={20} className="text-orange-400 mt-0.5" /> :
             status.has_upstream === false ? <XCircle size={20} className="text-yellow-400 mt-0.5" /> :
             <CheckCircle size={20} className="text-green-400 mt-0.5" />}
            <div className="flex-1 space-y-2">
              {status.has_upstream === false && (
                <p className="text-yellow-400 font-medium">
                  ⚠ Нет удалённого репозитория
                </p>
              )}
              {status.behind === 0 && status.has_upstream && (
                <p className="text-green-400 font-medium">
                  ✅ Актуальная версия &mdash; всё хорошо
                </p>
              )}
              {hasUpdates && (
                <>
                  <p className="text-orange-400 font-medium text-lg">
                    📦 Отставание на {status.behind} коммитов
                  </p>
                  <div className="bg-gray-900/80 rounded px-3 py-2 text-xs font-mono whitespace-pre-wrap max-h-24 overflow-auto text-gray-300 border border-gray-700">
                    {status.last_message}
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {status?.error && (
        <div className="bg-red-900/20 border border-red-700 rounded-lg p-4 text-red-400">
          ❌ {status.error}
        </div>
      )}

      {/* Diff */}
      {status?.diff_stats && !hasUpdates && (
        <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-3 text-xs font-mono whitespace-pre-wrap max-h-32 overflow-auto text-gray-400">
          {status.diff_stats}
        </div>
      )}

      {hasUpdates && (
        <>
          {/* Действия */}
          <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4 space-y-3">
            <h3 className="font-semibold text-sm text-gray-300">Действия</h3>
            <div className="flex flex-wrap gap-3">
              <button
                onClick={() => doPull(false)}
                disabled={loading}
                className="btn-primary bg-blue-600 hover:bg-blue-700 flex items-center gap-2"
              >
                <ArrowDown size={16} />
                {loading ? "⏳ Загрузка..." : "Применить (только код)"}
              </button>
              <button
                onClick={() => doPull(true)}
                disabled={loading}
                className="btn-primary bg-green-600 hover:bg-green-700 flex items-center gap-2"
              >
                <Server size={16} />
                Применить + пересобрать Docker
              </button>
              <button onClick={loadDiff} className="btn-secondary flex items-center gap-2">
                {showDiff ? <EyeOff size={16} /> : <Eye size={16} />}
                {showDiff ? "Скрыть diff" : "Посмотреть изменения"}
              </button>
            </div>
          </div>

          {showDiff && diff && (
            <div className="bg-gray-800/50 border border-gray-700 rounded-lg overflow-hidden">
              <div className="p-3 border-b border-gray-700 font-semibold text-sm text-gray-300">
                Изменения файлов
              </div>
              {diff.files && (
                <div className="px-3 py-2 text-xs font-mono whitespace-pre-wrap max-h-32 overflow-auto text-gray-300 bg-gray-900/50 border-b border-gray-700">
                  {diff.files}
                </div>
              )}
              {diff.stat && (
                <div className="px-3 py-2 text-xs font-mono whitespace-pre-wrap max-h-32 overflow-auto text-gray-400 bg-gray-900/30 border-b border-gray-700">
                  {diff.stat}
                </div>
              )}
              {diff.diff && (
                <details className="border-b border-gray-700">
                  <summary className="cursor-pointer text-sm text-blue-400 px-3 py-2 hover:bg-gray-700/30">
                    Полный diff
                  </summary>
                  <div className="px-3 py-2 text-xs font-mono whitespace-pre-wrap max-h-96 overflow-auto text-gray-300 bg-gray-900/50">
                    {diff.diff}
                  </div>
                </details>
              )}
              {diff.error && (
                <div className="px-3 py-2 text-red-400 text-sm">{diff.error}</div>
              )}
            </div>
          )}
        </>
      )}

      {/* Результат */}
      {pullResult && (
        <div className="bg-gray-800/50 border border-gray-700 rounded-lg overflow-hidden">
          <div className="p-3 border-b border-gray-700 font-semibold text-sm text-green-400 flex items-center gap-2">
            <CheckCircle size={16} />
            Результат применения
          </div>
          <div className="p-3 text-xs font-mono whitespace-pre-wrap max-h-48 overflow-auto text-gray-300">
            {pullResult}
          </div>
          <div className="p-3 border-t border-gray-700 text-xs text-gray-400 flex items-center gap-2">
            <Server size={12} />
            Для применения изменений может потребоваться перезапуск контейнера.
          </div>
        </div>
      )}

      {/* История */}
      {history.length > 0 && (
        <div className="bg-gray-800/50 border border-gray-700 rounded-lg overflow-hidden">
          <div className="p-3 border-b border-gray-700 font-semibold text-sm text-gray-300">
            История обновлений
          </div>
          <div className="divide-y divide-gray-700/50 max-h-36 overflow-auto">
            {history.map((h, i) => (
              <div key={i} className="px-3 py-1.5 text-xs text-gray-400 flex justify-between">
                <span>{h.time}</span>
                <span>{h.result}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
