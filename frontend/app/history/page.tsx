"use client";

import { useEffect, useState } from "react";
import { apiGetClient, apiPostClient } from "@/lib/api-client";
import { formatDate } from "@/lib/utils";
import { StatusBadge } from "@/components/Badge";
import { DataTable } from "@/components/DataTable";
import { OutputModal } from "@/components/Modal";
import { ReportsView } from "@/components/ReportsView";
import { SystemLogsView } from "@/components/SystemLogsView";
import { useToast } from "@/components/Toast";
import { Eye, Trash2 } from "lucide-react";

interface TaskRun {
  id: number;
  module_id: number;
  target_type: string;
  target_id: number;
  status: string;
  started_at?: string;
  finished_at?: string;
  created_at?: string;
  created_by?: string;
  stdout_text?: string;
  stderr_text?: string;
  per_host_json?: string;
}

interface Module {
  id: number;
  name: string;
  slug: string;
}

export default function HistoryPage() {
  const showToast = useToast();
  const [tab, setTab] = useState<"history" | "reports" | "logs">("history");
  const [runs, setRuns] = useState<TaskRun[]>([]);
  const [modules, setModules] = useState<Module[]>([]);
  const [modalText, setModalText] = useState("");
  const [modalTitle, setModalTitle] = useState("");

  async function load() {
    const [r, m] = await Promise.all([apiGetClient("/api/task-runs?limit=100"), apiGetClient("/api/modules")]);
    setRuns(r || []);
    setModules(m || []);
  }

  useEffect(() => {
    load();
    const wsUrl = `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}/api/python/ws`;
    const ws = new WebSocket(wsUrl);
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "task_status" && data.run) {
          setRuns((prev) => {
            const idx = prev.findIndex((x) => x.id === data.run.id);
            if (idx >= 0) {
              const next = [...prev];
              next[idx] = data.run;
              return next;
            }
            return [data.run, ...prev];
          });
        }
      } catch {}
    };
    return () => ws.close();
  }, []);

  async function clearHistory() {
    if (!confirm("Очистить всю историю выполненных задач?")) return;
    try {
      await apiPostClient("/api/task-runs/clear", {});
      showToast("История очищена");
      await load();
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  function openRunOutput(run: TaskRun) {
    const perHost = run.per_host_json ? JSON.parse(run.per_host_json) : [];
    const perHostText = perHost.length
      ? `\n\n--- По хостам ---\n${perHost
          .map(
            (item: any) =>
              `[${item.name || item.address || item.host_id || "Хост"}] ${item.address || ""}${item.port ? `:${item.port}` : ""}\n${item.output || "Нет вывода"}`
          )
          .join("\n\n")}`
      : "";
    const text = [run.stdout_text || "", run.stderr_text ? `--- stderr ---\n${run.stderr_text}` : "", perHostText]
      .filter(Boolean)
      .join("\n\n");
    setModalText(text || "Нет вывода");
    setModalTitle(`Результат задачи #${run.id}`);
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold">{tab === "history" ? "История" : tab === "reports" ? "Отчёты" : "Логи"}</h2>
        <p className="text-gray-500">
          {tab === "history" && "Журнал выполненных задач и их результатов"}
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

      {tab === "history" && (
      <div className="panel">
        <div className="flex justify-end mb-3">
          <button className="btn-secondary text-red-600" onClick={clearHistory}>
            <Trash2 size={16} /> Очистить
          </button>
        </div>
        <DataTable
          columns={[
            {
              title: "Модуль",
              render: (r) => modules.find((m) => m.id === r.module_id)?.name || r.module_id,
            },
            { title: "Цель", render: (r) => `${r.target_type}:${r.target_id}` },
            { title: "Статус", render: (r) => <StatusBadge status={r.status} /> },
            { title: "Запуск", render: (r) => formatDate(r.started_at || r.finished_at || r.created_at) },
            { title: "Инициатор", render: (r) => r.created_by || "—" },
            {
              title: "Результат",
              render: (r) => {
                const text = r.stdout_text || r.stderr_text || "";
                const perHost = r.per_host_json ? JSON.parse(r.per_host_json) : [];
                return (
                  <span className="inline-flex items-center gap-2">
                    <span className="max-w-xs truncate">{text}</span>
                    {perHost.length > 0 && <span className="text-gray-500 text-xs whitespace-nowrap">{perHost.length} хостов</span>}
                  </span>
                );
              },
            },
            {
              title: "",
              render: (r) => (
                <button className="btn-secondary p-2" onClick={() => openRunOutput(r)} title="Показать">
                  <Eye size={16} />
                </button>
              ),
            },
          ]}
          rows={runs}
        />
      </div>
      )}

      {modalText && <OutputModal text={modalText} title={modalTitle} onClose={() => setModalText("")} />}
    </div>
  );
}
