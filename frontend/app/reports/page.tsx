"use client";

import { useEffect, useState } from "react";
import { apiGetClient, apiPostClient, fetchReportFile } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { useToast } from "@/components/Toast";
import { OutputModal } from "@/components/Modal";
import { Eye, Trash2, Download } from "lucide-react";

interface Report {
  id: number;
  name: string;
  report_type: string;
  format: string;
  file_path: string;
  summary_json?: string;
  created_at: string;
}

interface TaskRun {
  id: number;
  module_id: number;
  target_type: string;
  target_id: number;
  status: string;
}

interface Module {
  id: number;
  name: string;
}

export default function ReportsPage() {
  const showToast = useToast();
  const [reports, setReports] = useState<Report[]>([]);
  const [taskRuns, setTaskRuns] = useState<TaskRun[]>([]);
  const [modules, setModules] = useState<Module[]>([]);
  const [taskRunId, setTaskRunId] = useState("");
  const [format, setFormat] = useState("txt");
  const [resultText, setResultText] = useState("");
  const [modalText, setModalText] = useState("");
  const [modalTitle, setModalTitle] = useState("");

  async function load() {
    const [r, t, m] = await Promise.all([apiGetClient("/api/reports"), apiGetClient("/api/task-runs?limit=100"), apiGetClient("/api/modules")]);
    setReports(r || []);
    setTaskRuns(t || []);
    setModules(m || []);
  }

  useEffect(() => {
    load();
  }, []);

  async function exportReport(e: React.FormEvent) {
    e.preventDefault();
    if (!taskRunId) {
      showToast("Выберите задачу", "error");
      return;
    }
    try {
      const result = await apiPostClient("/api/reports/export", { task_run_id: Number(taskRunId), format });
      const summary = result.report?.summary_json ? JSON.parse(result.report.summary_json) : {};
      setResultText(`Отчёт сформирован: ${result.file_path}\nзадача: ${summary.module_name || "—"}, хостов: ${summary.hosts || 0}, статус: ${summary.status || "—"}`);
      showToast("Отчёт сформирован");
      await load();
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  async function viewReport(filePath: string, name: string) {
    const fileName = filePath.replace(/^.*[\\/]/, "");
    try {
      const text = await fetchReportFile(fileName);
      setModalText(text);
      setModalTitle(name);
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  async function downloadReport(filePath: string, name: string) {
    const fileName = filePath.replace(/^.*[\\/]/, "");
    try {
      const text = await fetchReportFile(fileName);
      const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = fileName || `${name}.txt`;
      a.click();
      URL.revokeObjectURL(url);
      showToast("Отчёт сохранён");
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  async function clearReports() {
    if (!confirm("Все сформированные отчёты будут удалены. Продолжить?")) return;
    try {
      await apiPostClient("/api/reports/clear", {});
      showToast("Отчёты очищены");
      await load();
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  function reportSummary(report: Report) {
    try {
      const s = JSON.parse(report.summary_json || "{}");
      if (report.report_type === "host_status") return `хостов: ${s.total || 0}, доступно: ${s.active || 0}, недоступно: ${s.inactive || 0}`;
      if (report.report_type === "filesystem") return `хостов: ${s.hosts || 0}`;
      if (report.report_type === "task_history") return `запусков: ${s.total || 0}`;
      return `записей: ${s.rows || 0}`;
    } catch {
      return "";
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold">Отчёты</h2>
        <p className="text-gray-500">Формирование и просмотр файлов отчётности</p>
      </div>

      <div className="panel">
        <h3 className="font-semibold mb-4">Экспорт отчёта</h3>
        <form onSubmit={exportReport} className="grid md:grid-cols-3 gap-4 items-end">
          <label className="label">
            Исток задачи
            <select className="input" value={taskRunId} onChange={(e) => setTaskRunId(e.target.value)}>
              <option value="">Нет запусков</option>
              {taskRuns.map((r) => {
                const moduleName = modules.find((m) => m.id === r.module_id)?.name || r.module_id;
                const status = r.status === "success" ? "✓" : r.status === "error" ? "✗" : "○";
                return (
                  <option key={r.id} value={r.id}>
                    #{r.id} {status} {moduleName} → {r.target_type}:{r.target_id}
                  </option>
                );
              })}
            </select>
          </label>
          <label className="label">
            Формат
            <select className="input" value={format} onChange={(e) => setFormat(e.target.value)}>
              <option value="txt">TXT</option>
              <option value="csv">CSV</option>
              <option value="json">JSON</option>
            </select>
          </label>
          <button className="btn" type="submit">
            Сформировать
          </button>
        </form>
        {resultText && <pre className="mt-4 bg-slate-950 text-gray-200 rounded-[10px] p-4 text-sm min-h-[120px]">{resultText}</pre>}
      </div>

      <div className="panel">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold">Сформированные отчёты</h3>
          <button className="btn-secondary text-red-600" onClick={clearReports}>
            <Trash2 size={16} /> Очистить
          </button>
        </div>
        <div className="grid gap-3">
          {reports.length === 0 && <p className="text-gray-500">Нет сформированных отчётов</p>}
          {reports.map((r) => (
            <div
              key={r.id}
              className="flex items-center justify-between gap-3 p-4 border border-gray-200 rounded-2xl bg-white hover:bg-slate-50 transition"
            >
              <div className="min-w-0">
                <strong className="block truncate">{r.name || `Отчёт #${r.id}`}</strong>
                <span className="text-sm text-gray-500">
                  {formatDate(r.created_at)}
                  {reportSummary(r) ? ` • ${reportSummary(r)}` : ""}
                </span>
              </div>
              <div className="flex gap-2">
                <button className="btn-secondary p-2" onClick={() => viewReport(r.file_path, r.name || `Отчёт #${r.id}`)} title="Просмотр">
                  <Eye size={16} />
                </button>
                <button className="btn-secondary p-2" onClick={() => downloadReport(r.file_path, r.name || `Отчёт #${r.id}`)} title="Скачать">
                  <Download size={16} />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {modalText && <OutputModal text={modalText} title={modalTitle} onClose={() => setModalText("")} />}
    </div>
  );
}
