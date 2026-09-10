"use client";

import { useEffect, useState, useCallback } from "react";
import { apiGetClient, apiPostClient } from "@/lib/api-client";
import { useAuth } from "@/components/AuthProvider";
import { useToast } from "@/components/Toast";
import { DataTable } from "@/components/DataTable";
import { Modal } from "@/components/Modal";
import { formatDate } from "@/lib/utils";
import { ShieldOff, Shield, Trash2, Settings, Network, Download, Upload } from "lucide-react";
import {
  fetchExecutionSettings,
  saveExecutionSettings,
  type ExecutionField,
  type SshUserMode,
} from "@/lib/execution-settings";
import { useRouter } from "next/navigation";
import { useRef } from "react";

interface User {
  id: number;
  username: string;
  is_active: number;
  is_superuser: number;
  role?: string;
  created_at: string;
}

interface ModuleAccess {
  module_id: number;
  name: string;
  slug: string;
  is_enabled: number;
  allowed: number;
}

interface GroupAccess {
  group_id: number;
  name: string;
  kind: string;
  granted: boolean;
}

interface DbTable {
  table: string;
  rows: number;
}

type BackupMode = "full" | "tables";
type RestoreMode = "classic" | "replace" | "append";

const TABLE_LABELS: Record<string, string> = {
  ssh_keys: "SSH-ключи",
  groups: "Группы хостов",
  modules: "Модули",
  users: "Пользователи",
  hosts: "Хосты",
  boards: "Доски",
  inventory_snapshots: "Инвентаризация",
  task_runs: "История запусков",
  scheduled_tasks: "Расписания",
  reports: "Отчёты",
  group_hosts: "Связи хост↔группа",
  board_hosts: "Хосты на досках",
  user_group_access: "Доступ к группам",
  user_module_access: "Доступ к модулям",
};

const RESTORE_MODE_INFO: Record<RestoreMode, { label: string; desc: string; danger: boolean }> = {
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

export default function AdminPage() {
  const { user } = useAuth();
  const router = useRouter();
  const showToast = useToast();
  const [users, setUsers] = useState<User[]>([]);
  const [modulesUser, setModulesUser] = useState<User | null>(null);
  const [modules, setModules] = useState<ModuleAccess[]>([]);
  const [groupsUser, setGroupsUser] = useState<User | null>(null);
  const [groups, setGroups] = useState<GroupAccess[]>([]);
  const [restoring, setRestoring] = useState(false);
  const restoreInputRef = useRef<HTMLInputElement>(null);
  const [backupMode, setBackupMode] = useState<BackupMode>("full");
  const [dbTables, setDbTables] = useState<DbTable[]>([]);
  const [selectedTables, setSelectedTables] = useState<Set<string>>(new Set());
  const [restoreMode, setRestoreMode] = useState<RestoreMode>("classic");
  const [defaultCreds, setDefaultCreds] = useState<{ username: string; has_password: boolean }>({ username: "", has_password: false });
  const [credsSaving, setCredsSaving] = useState(false);
  // Пользователь исполнения команд — глобальная настройка на сервере
  // (services/execution_settings.py). Значение и подпись приходят с сервера.
  const [sshUserMode, setSshUserMode] = useState<SshUserMode>("service");
  const [sshUserField, setSshUserField] = useState<ExecutionField | null>(null);
  const [execSaving, setExecSaving] = useState(false);

  useEffect(() => {
    if (user && !user.is_superuser) {
      router.push("/");
    }
  }, [user, router]);

  const loadUsers = useCallback(async () => {
    try {
      const data = await apiGetClient("/api/admin/users");
      setUsers(data || []);
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }, [showToast]);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  const loadDefaultCreds = useCallback(async () => {
    try {
      const data = await apiGetClient("/api/default-creds");
      setDefaultCreds(data || { username: "", has_password: false });
    } catch (err: any) {
      setDefaultCreds({ username: "", has_password: false });
    }
  }, []);

  useEffect(() => {
    loadDefaultCreds();
  }, [loadDefaultCreds]);

  const loadExecutionSettings = useCallback(async () => {
    try {
      const data = await fetchExecutionSettings();
      setSshUserMode((data?.config?.ssh_user_mode as SshUserMode) || "service");
      setSshUserField(data?.schema?.ssh_user_mode || null);
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }, [showToast]);

  useEffect(() => {
    loadExecutionSettings();
  }, [loadExecutionSettings]);

  async function changeSshUserMode(mode: SshUserMode) {
    if (mode === sshUserMode) return;
    const prev = sshUserMode;
    setSshUserMode(mode);
    setExecSaving(true);
    try {
      const res = await saveExecutionSettings({ ssh_user_mode: mode });
      setSshUserMode((res?.config?.ssh_user_mode as SshUserMode) || mode);
      showToast("Пользователь исполнения обновлён");
    } catch (err: any) {
      setSshUserMode(prev);
      showToast(err.message, "error");
    } finally {
      setExecSaving(false);
    }
  }

  async function saveDefaultCreds(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const fd = new FormData(form);
    const username = String(fd.get("default_username") || "").trim();
    const password = String(fd.get("default_password") || "");
    setCredsSaving(true);
    try {
      const body: Record<string, string> = {};
      // Всегда отправляем username (актуальный), пароль — только если введён.
      body.username = username;
      if (password) body.password = password;
      const res = await apiPostClient("/api/default-creds/update", body);
      setDefaultCreds({ username: res?.username ?? username, has_password: res?.has_password ?? false });
      showToast("Стандартные креды сохранены");
      form.reset();
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setCredsSaving(false);
    }
  }

  async function onCreateUser(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const fd = new FormData(form);
    try {
      await apiPostClient("/api/admin/users", {
        username: fd.get("username"),
        password: fd.get("password"),
        role: fd.get("role") || "user",
      });
      showToast("Пользователь создан");
      form.reset();
      await loadUsers();
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  async function toggleActive(u: User) {
    try {
      await apiPostClient("/api/admin/users/update", { id: u.id, is_active: u.is_active ? 0 : 1 });
      showToast(u.is_active ? "Пользователь отключён" : "Пользователь включён");
      await loadUsers();
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  async function changeRole(u: User, role: string) {
    try {
      await apiPostClient("/api/admin/users/update", { id: u.id, role });
      await loadUsers();
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  async function deleteUser(u: User) {
    if (!confirm(`Удалить пользователя "${u.username}"?`)) return;
    try {
      await apiPostClient("/api/admin/users/delete", { id: u.id });
      showToast("Пользователь удалён");
      await loadUsers();
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  async function openModules(u: User) {
    setModulesUser(u);
    try {
      const data = await apiGetClient(`/api/admin/user-modules?user_id=${u.id}`);
      setModules(data || []);
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  async function setModuleAccess(moduleId: number, allowed: boolean) {
    if (!modulesUser) return;
    try {
      await apiPostClient("/api/admin/user-modules", {
        user_id: modulesUser.id,
        module_id: moduleId,
        allowed: allowed ? 1 : 0,
      });
      setModules((prev) =>
        prev.map((m) => (m.module_id === moduleId ? { ...m, allowed: allowed ? 1 : 0 } : m))
      );
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  async function openGroups(u: User) {
    setGroupsUser(u);
    try {
      const data = await apiGetClient(`/api/admin/user-groups?user_id=${u.id}`);
      setGroups(data || []);
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  async function setGroupAccess(groupId: number, granted: boolean) {
    if (!groupsUser) return;
    try {
      await apiPostClient("/api/admin/user-groups", {
        user_id: groupsUser.id,
        group_id: groupId,
        granted,
      });
      setGroups((prev) =>
        prev.map((g) => (g.group_id === groupId ? { ...g, granted } : g))
      );
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

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
    if (mode === "tables" && dbTables.length === 0) {
      loadDbTables();
    }
  }

  function toggleTable(table: string) {
    setSelectedTables((prev) => {
      const next = new Set(prev);
      if (next.has(table)) next.delete(table);
      else next.add(table);
      return next;
    });
  }

  async function downloadBackup() {
    if (backupMode === "tables" && selectedTables.size === 0) {
      showToast("Выберите хотя бы одну таблицу", "error");
      return;
    }
    try {
      const query =
        backupMode === "tables"
          ? `?tables=${encodeURIComponent(Array.from(selectedTables).join(","))}`
          : "";
      const res = await fetch(`/api/python/api/admin/backup${query}`, { credentials: "include" });
      if (!res.ok) {
        const data = await res.json();
        showToast(data.error || "Ошибка бэкапа", "error");
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const ts = new Date().toISOString().slice(0, 19).replace(/[T:]/g, "-");
      const suffix = backupMode === "tables" ? "_partial" : "";
      a.download = `netrunner_backup${suffix}_${ts}.db`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  async function uploadRestore(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const info = RESTORE_MODE_INFO[restoreMode];
    const prompt = info.danger
      ? `Восстановить базу из "${file.name}" в режиме «${info.label}»?\n\n${info.desc}\n\nДействие необратимо. Сервер перезапустится.`
      : `Восстановить базу из "${file.name}" в режиме «${info.label}»?\n\n${info.desc}\n\nСервер перезапустится.`;
    if (!confirm(prompt)) {
      e.target.value = "";
      return;
    }
    setRestoring(true);
    try {
      const fd = new FormData();
      fd.append("mode", restoreMode);
      fd.append("file", file);
      const res = await fetch("/api/python/api/admin/restore", {
        method: "POST",
        credentials: "include",
        body: fd,
      });
      const data = await res.json();
      if (!data.ok) {
        showToast(data.error || "Ошибка восстановления", "error");
        return;
      }
      showToast(data.message || "База восстановлена. Перезагрузка...");
      setTimeout(() => window.location.reload(), 3000);
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setRestoring(false);
      e.target.value = "";
    }
  }

  if (!user?.is_superuser) return null;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold">Администрирование</h2>
        <p className="text-gray-500">Управление пользователями и доступом к модулям</p>
      </div>

      <div className="panel">
        <h3 className="font-semibold mb-4">Добавить пользователя</h3>
        <form onSubmit={onCreateUser} className="grid sm:grid-cols-2 gap-4 items-end">
          <label className="label">
            Имя пользователя
            <input className="input" name="username" placeholder="ivan" required />
          </label>
          <label className="label">
            Пароль
            <input className="input" name="password" type="password" placeholder="••••••" required />
          </label>
          <label className="label">
            Роль
            <select className="input" name="role" defaultValue="user">
              <option value="user">Пользователь</option>
              <option value="teacher">Преподаватель</option>
              <option value="admin">Администратор</option>
            </select>
          </label>
          <button className="btn" type="submit">
            Добавить
          </button>
        </form>

        <h3 className="font-semibold mb-4 mt-6 pt-6 border-t border-gray-200 dark:border-gray-700">Пользователи</h3>
        <DataTable
          columns={[
            { title: "ID", key: "id" },
            { title: "Имя пользователя", key: "username" },
            {
              title: "Роль",
              render: (u) => {
                if (u.is_superuser) return <span className="badge badge-running">admin</span>;
                if (u.role === "teacher") return <span className="badge badge-pending">teacher</span>;
                return <span className="badge">user</span>;
              },
            },
            {
              title: "Статус",
              render: (u) =>
                u.is_active ? (
                  <span className="badge badge-success">Активен</span>
                ) : (
                  <span className="badge badge-error">Отключён</span>
                ),
            },
            { title: "Создан", render: (u) => formatDate(u.created_at) },
            {
              title: "",
              render: (u) => {
                // Бутстрап-аккаунт admin/admin (is_superuser=1, роль ещё не 'admin')
                // защищён от управления через UI — иначе можно случайно остаться без
                // единственного суперпользователя. Роль 'admin', назначенная явно
                // другому аккаунту, управляется как обычная роль.
                const isBootstrapAdmin = Boolean(u.is_superuser) && u.role !== "admin";
                return (
                <div className="flex gap-2 justify-end">
                  {!isBootstrapAdmin && (
                    <select
                      className="input py-1 px-2 text-xs w-32"
                      value={u.role || "user"}
                      onChange={(e) => changeRole(u, e.target.value)}
                    >
                      <option value="user">user</option>
                      <option value="teacher">teacher</option>
                      <option value="admin">admin</option>
                    </select>
                  )}
                  <button
                    className="btn-secondary p-2"
                    title="Доступ к группам хостов"
                    onClick={() => openGroups(u)}
                  >
                    <Network size={16} />
                  </button>
                  <button
                    className="btn-secondary p-2"
                    title="Управление модулями"
                    onClick={() => openModules(u)}
                  >
                    <Settings size={16} />
                  </button>
                  {!isBootstrapAdmin && (
                    <button
                      className="btn-secondary p-2"
                      title={u.is_active ? "Отключить" : "Включить"}
                      onClick={() => toggleActive(u)}
                    >
                      {u.is_active ? <ShieldOff size={16} /> : <Shield size={16} />}
                    </button>
                  )}
                  {!isBootstrapAdmin && (
                    <button
                      className="btn-secondary p-2 text-red-600"
                      title="Удалить"
                      onClick={() => deleteUser(u)}
                    >
                      <Trash2 size={16} />
                    </button>
                  )}
                </div>
                );
              },
            },
          ]}
          rows={users}
        />
      </div>

      <div className="grid md:grid-cols-2 gap-6 items-start">
        <div className="grid gap-6">
          <div className="panel">
            <h3 className="font-semibold mb-1">Резервное копирование</h3>
            <p className="text-sm text-gray-500 mb-4">
              Полный бэкап создаётся через SQLite Online Backup API — безопасно на живой
              базе. Частичный бэкап содержит полную схему, но только выбранные таблицы.
            </p>

            <div className="flex gap-4 mb-3">
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input
                  type="radio"
                  name="backupMode"
                  className="accent-blue-600"
                  checked={backupMode === "full"}
                  onChange={() => chooseBackupMode("full")}
                />
                Полный бэкап
              </label>
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input
                  type="radio"
                  name="backupMode"
                  className="accent-blue-600"
                  checked={backupMode === "tables"}
                  onChange={() => chooseBackupMode("tables")}
                />
                Выбранные таблицы
              </label>
            </div>

            {backupMode === "tables" && (
              <div className="mb-4 border border-gray-200 rounded-[10px] p-3 max-h-[40vh] overflow-y-auto">
                {dbTables.length === 0 ? (
                  <p className="text-sm text-gray-500">Загрузка таблиц…</p>
                ) : (
                  <div className="grid sm:grid-cols-2 gap-2">
                    {dbTables.map((t) => (
                      <label
                        key={t.table}
                        className="flex items-center gap-2 text-sm cursor-pointer p-1.5 rounded hover:bg-gray-50"
                      >
                        <input
                          type="checkbox"
                          className="w-4 h-4 accent-blue-600"
                          checked={selectedTables.has(t.table)}
                          onChange={() => toggleTable(t.table)}
                        />
                        <span className="flex-1">{TABLE_LABELS[t.table] || t.table}</span>
                        <span className="text-xs text-gray-400">{t.rows}</span>
                      </label>
                    ))}
                  </div>
                )}
              </div>
            )}

            <div>
              <button className="btn flex items-center gap-2" onClick={downloadBackup}>
                <Download size={16} />
                Скачать бэкап
              </button>
            </div>
          </div>
          {/* Стандартные креды — отдельный блок под «Резервным копированием» */}
      <div className="panel">
        <h3 className="font-semibold mb-1">Стандартные креды</h3>
        <p className="text-sm text-gray-500 mb-4">
          Используются при добавлении хоста, если его поля «Пользователь» и «Пароль»
          не заполнены. Пароль хранится зашифрованным.
        </p>
        <form onSubmit={saveDefaultCreds} className="grid sm:grid-cols-3 gap-4 items-end max-w-3xl">
          <label className="label">
            Пользователь
            <input
              className="input"
              name="default_username"
              placeholder={defaultCreds.username ? defaultCreds.username : "не задан"}
              autoComplete="off"
            />
          </label>
          <label className="label">
            Пароль
            <input
              className="input"
              name="default_password"
              type="password"
              placeholder="•••••"
              autoComplete="new-password"
            />
          </label>
          <button className="btn" type="submit" disabled={credsSaving}>
            {credsSaving ? "Сохранение..." : "Сохранить"}
          </button>
        </form>
      </div>

      {/* Пользователь исполнения команд — глобальный переключатель на сервере.
          Меняет, от чьего имени NetRunner выполняет SSH-команды на целевых
          машинах; на самих хостах при этом ничего не меняется. */}
      <div className="panel">
        <h3 className="font-semibold mb-1">
          {sshUserField?.label || "Пользователь исполнения команд"}
        </h3>
        <p className="text-sm text-gray-500 mb-4">
          {sshUserField?.hint ||
            "От чьего имени выполняются команды на целевых машинах."}
        </p>
        <div className="flex gap-3 flex-wrap">
          {(
            sshUserField?.choices || [
              { value: "service", label: "Сервисный (netrunner-svc)" },
              { value: "primary", label: "Первичный пользователь хоста" },
            ]
          ).map((choice) => (
            <label
              key={choice.value}
              className={`flex items-center gap-2 text-sm cursor-pointer px-3 py-2 rounded-[10px] border transition-colors ${
                sshUserMode === choice.value
                  ? "border-blue-500 bg-blue-50"
                  : "border-gray-200 hover:bg-gray-50"
              } ${execSaving ? "opacity-60" : ""}`}
            >
              <input
                type="radio"
                name="sshUserMode"
                className="accent-blue-600"
                checked={sshUserMode === choice.value}
                disabled={execSaving}
                onChange={() => changeSshUserMode(choice.value as SshUserMode)}
              />
              {choice.label}
            </label>
          ))}
        </div>
      </div>
        </div>
        <div className="panel">
          <h3 className="font-semibold mb-1">Восстановление</h3>
          <p className="text-sm text-gray-500 mb-3">
            После восстановления сервер автоматически перезапустится. Перед операцией
            сохраняется копия текущей базы (<code>.pre_restore</code>).
          </p>

          <div className="space-y-2 mb-3 max-w-2xl">
            {(Object.keys(RESTORE_MODE_INFO) as RestoreMode[]).map((mode) => {
              const info = RESTORE_MODE_INFO[mode];
              return (
                <label
                  key={mode}
                  className={`flex items-start gap-3 p-3 rounded-[10px] border cursor-pointer ${
                    restoreMode === mode ? "border-blue-500 bg-blue-50" : "border-gray-200 hover:bg-gray-50"
                  }`}
                >
                  <input
                    type="radio"
                    name="restoreMode"
                    className="accent-blue-600 mt-0.5"
                    checked={restoreMode === mode}
                    onChange={() => setRestoreMode(mode)}
                  />
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

          <button
            className="btn-secondary flex items-center gap-2"
            onClick={() => restoreInputRef.current?.click()}
            disabled={restoring}
          >
            <Upload size={16} />
            {restoring ? "Восстановление…" : "Выбрать файл и восстановить"}
          </button>
          <input
            ref={restoreInputRef}
            type="file"
            accept=".db"
            className="hidden"
            onChange={uploadRestore}
          />
        </div>
      </div>

      {modulesUser && (
        <Modal
          title={`Доступ к модулям — ${modulesUser.username}`}
          onClose={() => setModulesUser(null)}
        >
          <div className="space-y-2 max-h-[60vh] overflow-y-auto pr-1">
            {modules.length === 0 && (
              <p className="text-gray-500 text-sm">Нет модулей</p>
            )}
            {modules.map((m) => (
              <label
                key={m.module_id}
                className="flex items-center gap-3 p-3 rounded-[10px] border border-gray-200 cursor-pointer hover:bg-gray-50"
              >
                <input
                  type="checkbox"
                  checked={Boolean(m.allowed)}
                  onChange={(e) => setModuleAccess(m.module_id, e.target.checked)}
                  className="w-4 h-4 accent-blue-600"
                />
                <span className="text-sm font-medium flex-1">{m.name}</span>
                <code className="text-xs text-gray-400">{m.slug}</code>
                {!m.is_enabled && (
                  <span className="badge text-xs">отключён</span>
                )}
              </label>
            ))}
          </div>
        </Modal>
      )}

      {groupsUser && (
        <Modal
          title={`Доступ к группам хостов — ${groupsUser.username}`}
          onClose={() => setGroupsUser(null)}
        >
          <p className="text-xs text-gray-500 mb-3">
            Если ни одна группа не отмечена — пользователь видит все хосты.
          </p>
          <div className="space-y-2 max-h-[60vh] overflow-y-auto pr-1">
            {groups.length === 0 && (
              <p className="text-gray-500 text-sm">Нет групп хостов</p>
            )}
            {groups.map((g) => (
              <label
                key={g.group_id}
                className="flex items-center gap-3 p-3 rounded-[10px] border border-gray-200 cursor-pointer hover:bg-gray-50"
              >
                <input
                  type="checkbox"
                  checked={g.granted}
                  onChange={(e) => setGroupAccess(g.group_id, e.target.checked)}
                  className="w-4 h-4 accent-blue-600"
                />
                <span className="text-sm font-medium flex-1">{g.name}</span>
                <code className="text-xs text-gray-400">{g.kind}</code>
              </label>
            ))}
          </div>
        </Modal>
      )}
    </div>
  );
}
