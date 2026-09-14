"use client";

import { useState, useCallback, useRef } from "react";
import { apiGetClient } from "@/lib/api-client";
import { useToast } from "@/components/Toast";
import { Download, Upload } from "lucide-react";

interface DbTable {
  table: string;
  rows: number;
}

type BackupMode = "full" | "tables";
type RestoreMode = "classic" | "replace" | "append";

const TABLE_LABELS: Record<string, string> = {
  ssh_keys: "SSH-ключи",
  groups: "Кабинеты",
  modules: "Модули",
  users: "Пользователи",
  hosts: "Хосты",
  boards: "Доски",
  inventory_snapshots: "Инвентаризация",
  task_runs: "История запусков",
  scheduled_tasks: "Расписания",
  reports: "Отчёты",
  group_hosts: "Связи хост-кабинет",
  board_hosts: "Хосты на досках",
  user_group_access: "Доступ к кабинетам",
  user_module_access: "Доступ к модулям",
};

const RESTORE_MODES: Record<RestoreMode, { label: string; desc: string; danger: boolean }> = {
  classic: {
    label: "Классическое",
    desc: "Полная замена базы файлом. Все текущие данные будут потеряны.",
    danger: true,
  },
  replace: {
    label: "Замена по id",
    desc: "Перезапись записей с тем же id. Записи, которых нет в файле, останутся.",
    danger: false,
  },
  append: {
    label: "Дополнение",
    desc: "Добавление записей из файла с новыми id. Возможны дубликаты; конфликтующие имена получат суффикс «(копия)».",
    danger: false,
  },
};

export function DatabaseTab() {
  const showToast = useToast();
  const restoreInputRef = useRef<HTMLInputElement>(null);

  const [backupMode, setBackupMode] = useState<BackupMode>("full");
  const [dbTables, setDbTables] = useState<DbTable[]>([]);
  const [selectedTables, setSelectedTables] = useState<Set<string>>(new Set());
  const [restoreMode, setRestoreMode] = useState<RestoreMode>("classic");
  const [restoring, setRestoring] = useState(false);

  const loadDbTables = useCallback(async () => {
    try {
      const data = await apiGetClient("/api/admin/db-tables");
      setDbTables(data || []);
      setSelectedTables(new Set((data || []).map((t: DbTable) => t.table)));
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }, [showToast]);

  function chooseBackupMode(mode: BackupMode) {
    setBackupMode(mode);
    if (mode === "tables" && dbTables.length === 0) loadDbTables();
  }

  function toggleTable(table: string) {
    setSelectedTables((prev) => {
      const next = new Set(prev);
      if (next.has(table)) next.delete(table); else next.add(table);
      return next;
    });
  }

  async function downloadBackup() {
    if (backupMode === "tables" && selectedTables.size === 0) {
      showToast("Выберите хотя бы одну таблицу", "error");
      return;
    }
    try {
      const query = backupMode === "tables" ? `?tables=${encodeURIComponent(Array.from(selectedTables).join(","))}` : "";
      const res = await fetch(`/api/python/api/admin/backup${query}`, { credentials: "include" });
      if (!res.ok) { showToast((await res.json()).error || "Ошибка бэкапа", "error"); return; }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const ts = new Date().toISOString().slice(0, 19).replace(/[T:]/g, "-");
      a.download = `netrunner_backup${backupMode === "tables" ? "_partial" : ""}_${ts}.db`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  async function uploadRestore(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const info = RESTORE_MODES[restoreMode];
    const msg = info.danger
      ? `Восстановить базу из "${file.name}" в режиме «${info.label}»?\n\n${info.desc}\n\nДействие необратимо. Сервер перезапустится.`
      : `Восстановить базу из "${file.name}" в режиме «${info.label}»?\n\n${info.desc}\n\nСервер перезапустится.`;
    if (!confirm(msg)) { e.target.value = ""; return; }
    setRestoring(true);
    try {
      const fd = new FormData();
      fd.append("mode", restoreMode);
      fd.append("file", file);
      const res = await fetch("/api/python/api/admin/restore", { method: "POST", credentials: "include", body: fd });
      const data = await res.json();
      if (!data.ok) { showToast(data.error || "Ошибка восстановления", "error"); return; }
      showToast(data.message || "База восстановлена. Перезагрузка...");
      setTimeout(() => window.location.reload(), 3000);
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setRestoring(false);
      e.target.value = "";
    }
  }

  return (
    <div className="grid md:grid-cols-2 gap-6 items-start">
      <div className="panel">
        <h3 className="font-semibold mb-1">Резервное копирование</h3>
        <p className="text-sm text-gray-500 mb-4">
          Полный бэкап через SQLite Online Backup API — безопасно на живой базе. Частичный — только выбранные таблицы.
        </p>
        <div className="flex gap-4 mb-3">
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input type="radio" name="backupMode" className="accent-blue-600" checked={backupMode === "full"} onChange={() => chooseBackupMode("full")} />
            Полный бэкап
          </label>
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input type="radio" name="backupMode" className="accent-blue-600" checked={backupMode === "tables"} onChange={() => chooseBackupMode("tables")} />
            Выбранные таблицы
          </label>
        </div>
        {backupMode === "tables" && (
          <div className="mb-4 border border-gray-200 dark:border-gray-700 rounded-[10px] p-3 max-h-[40vh] overflow-y-auto">
            {dbTables.length === 0
              ? <p className="text-sm text-gray-500">Загрузка таблиц…</p>
              : (
                <div className="grid sm:grid-cols-2 gap-2">
                  {dbTables.map((t) => (
                    <label key={t.table} className="flex items-center gap-2 text-sm cursor-pointer p-1.5 rounded hover:bg-gray-50 dark:hover:bg-gray-800">
                      <input type="checkbox" className="w-4 h-4 accent-blue-600" checked={selectedTables.has(t.table)} onChange={() => toggleTable(t.table)} />
                      <span className="flex-1">{TABLE_LABELS[t.table] || t.table}</span>
                      <span className="text-xs text-gray-400">{t.rows}</span>
                    </label>
                  ))}
                </div>
              )}
          </div>
        )}
        <button className="btn flex items-center gap-2" onClick={downloadBackup}>
          <Download size={16} /> Скачать бэкап
        </button>
      </div>

      <div className="panel">
        <h3 className="font-semibold mb-1">Восстановление</h3>
        <p className="text-sm text-gray-500 mb-3">
          После восстановления сервер автоматически перезапустится. Перед операцией сохраняется копия текущей базы (<code>.pre_restore</code>).
        </p>
        <div className="space-y-2 mb-4">
          {(Object.keys(RESTORE_MODES) as RestoreMode[]).map((mode) => {
            const info = RESTORE_MODES[mode];
            return (
              <label key={mode} className={`flex items-start gap-3 p-3 rounded-[10px] border cursor-pointer transition-colors ${restoreMode === mode ? "border-blue-500 bg-blue-50 dark:bg-blue-950/30" : "border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800"}`}>
                <input type="radio" name="restoreMode" className="accent-blue-600 mt-0.5" checked={restoreMode === mode} onChange={() => setRestoreMode(mode)} />
                <span className="flex-1">
                  <span className="text-sm font-medium flex items-center gap-2">
                    {info.label}
                    {info.danger && <span className="badge badge-error text-xs">деструктивно</span>}
                  </span>
                  <span className="block text-xs text-gray-500 mt-0.5">{info.desc}</span>
                </span>
              </label>
            );
          })}
        </div>
        <button className="btn-secondary flex items-center gap-2" onClick={() => restoreInputRef.current?.click()} disabled={restoring}>
          <Upload size={16} /> {restoring ? "Восстановление…" : "Выбрать файл и восстановить"}
        </button>
        <input ref={restoreInputRef} type="file" accept=".db" className="hidden" onChange={uploadRestore} />
      </div>
    </div>
  );
}
