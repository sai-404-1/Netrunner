"use client";

import { useState } from "react";
import { SystemLogsView } from "@/components/SystemLogsView";
import { ReportsView } from "@/components/ReportsView";
import { HistoryView } from "@/components/HistoryView";

export default function HistoryPage() {
  const [tab, setTab] = useState<"history" | "reports" | "logs">("history");

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold">{tab === "history" ? "История" : tab === "reports" ? "Отчёты" : "Логи"}</h2>
        <p className="text-gray-500">
          {tab === "history" && "Общая лента событий всех сервисов NetRunner"}
          {tab === "reports" && "Формирование и просмотр файлов отчётности"}
          {tab === "logs" && "Журнал внутренних процессов сервера (например, установка агентов на хосты)"}
        </p>
      </div>

      {/* Вкладки: История / Отчёты / Логи */}
      <div className="flex items-center gap-1 border-b border-gray-200 dark:border-gray-700">
        <button
          onClick={() => setTab("history")}
          className={`px-4 py-2 text-sm font-semibold border-b-2 -mb-px transition-colors ${
            tab === "history" ? "border-blue-600 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700"
          }`}
        >
          История
        </button>
        <button
          onClick={() => setTab("reports")}
          className={`px-4 py-2 text-sm font-semibold border-b-2 -mb-px transition-colors ${
            tab === "reports" ? "border-blue-600 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700"
          }`}
        >
          Отчёты
        </button>
        <button
          onClick={() => setTab("logs")}
          className={`px-4 py-2 text-sm font-semibold border-b-2 -mb-px transition-colors ${
            tab === "logs" ? "border-blue-600 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700"
          }`}
        >
          Логи
        </button>
      </div>

      {tab === "reports" && <ReportsView />}
      {tab === "logs" && <SystemLogsView />}
      {tab === "history" && <HistoryView />}
    </div>
  );
}
