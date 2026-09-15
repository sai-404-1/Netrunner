"use client";

import { useEffect, useState, useCallback } from "react";
import { apiGetClient, apiPostClient } from "@/lib/api-client";
import { useToast } from "@/components/Toast";
import { DataTable } from "@/components/DataTable";
import { Modal } from "@/components/Modal";
import { formatDate } from "@/lib/utils";
import { ShieldOff, Shield, Trash2, Settings, Network } from "lucide-react";

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

export function UsersTab() {
  const showToast = useToast();
  const [users, setUsers] = useState<User[]>([]);
  const [modulesUser, setModulesUser] = useState<User | null>(null);
  const [modules, setModules] = useState<ModuleAccess[]>([]);
  const [groupsUser, setGroupsUser] = useState<User | null>(null);
  const [groups, setGroups] = useState<GroupAccess[]>([]);

  const loadUsers = useCallback(async () => {
    try {
      const data = await apiGetClient("/api/admin/users");
      setUsers(data || []);
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }, [showToast]);

  useEffect(() => { loadUsers(); }, [loadUsers]);

  async function onCreateUser(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    try {
      await apiPostClient("/api/admin/users", {
        username: fd.get("username"),
        password: fd.get("password"),
        role: fd.get("role") || "user",
      });
      showToast("Пользователь создан");
      (e.currentTarget as HTMLFormElement).reset();
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
      await apiPostClient("/api/admin/user-modules", { user_id: modulesUser.id, module_id: moduleId, allowed: allowed ? 1 : 0 });
      setModules((prev) => prev.map((m) => (m.module_id === moduleId ? { ...m, allowed: allowed ? 1 : 0 } : m)));
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
      await apiPostClient("/api/admin/user-groups", { user_id: groupsUser.id, group_id: groupId, granted });
      setGroups((prev) => prev.map((g) => (g.group_id === groupId ? { ...g, granted } : g)));
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  return (
    <div className="space-y-6">
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
            <select className="input appearance-none" name="role" defaultValue="user">
              <option value="user">Пользователь</option>
              <option value="teacher">Преподаватель</option>
              <option value="admin">Администратор</option>
            </select>
          </label>
          <button className="btn" type="submit">Добавить</button>
        </form>
      </div>

      <div className="panel">
        <h3 className="font-semibold mb-4">Пользователи</h3>
        <DataTable
          columns={[
            { title: "ID", key: "id" },
            { title: "Имя", key: "username" },
            {
              title: "Роль",
              render: (u) => {
                if (u.is_superuser) return <span className="badge badge-running">superuser</span>;
                if (u.role === "teacher") return <span className="badge badge-success">teacher</span>;
                if (u.role === "admin") return <span className="badge badge-running">admin</span>;
                return <span className="badge">user</span>;
              },
            },
            {
              title: "Статус",
              render: (u) => u.is_active
                ? <span className="badge badge-success">Активен</span>
                : <span className="badge badge-error">Отключён</span>,
            },
            { title: "Создан", render: (u) => formatDate(u.created_at) },
            {
              title: "",
              render: (u) => {
                const isBootstrapAdmin = Boolean(u.is_superuser) && u.role !== "admin";
                return (
                  <div className="flex gap-2 justify-end">
                    {!isBootstrapAdmin && (
                      <select
                        className="input py-1 px-2 text-xs w-32 appearance-none"
                        value={u.role || "user"}
                        onChange={(e) => changeRole(u, e.target.value)}
                      >
                        <option value="user">user</option>
                        <option value="teacher">teacher</option>
                        <option value="admin">admin</option>
                      </select>
                    )}
                    <button className="btn-secondary p-2" title="Доступ к кабинетам" onClick={() => openGroups(u)}>
                      <Network size={16} />
                    </button>
                    <button className="btn-secondary p-2" title="Доступ к модулям" onClick={() => openModules(u)}>
                      <Settings size={16} />
                    </button>
                    {!isBootstrapAdmin && (
                      <button className="btn-secondary p-2" title={u.is_active ? "Отключить" : "Включить"} onClick={() => toggleActive(u)}>
                        {u.is_active ? <ShieldOff size={16} /> : <Shield size={16} />}
                      </button>
                    )}
                    {!isBootstrapAdmin && (
                      <button className="btn-secondary p-2 text-red-600" title="Удалить" onClick={() => deleteUser(u)}>
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

      {modulesUser && (
        <Modal title={`Доступ к модулям — ${modulesUser.username}`} onClose={() => setModulesUser(null)}>
          <div className="space-y-2 max-h-[60vh] overflow-y-auto pr-1">
            {modules.length === 0 && <p className="text-gray-500 text-sm">Нет модулей</p>}
            {modules.map((m) => (
              <label key={m.module_id} className="flex items-center gap-3 p-3 rounded-[10px] border border-gray-200 dark:border-gray-700 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800">
                <input type="checkbox" checked={Boolean(m.allowed)} onChange={(e) => setModuleAccess(m.module_id, e.target.checked)} className="w-4 h-4 accent-blue-600" />
                <span className="text-sm font-medium flex-1">{m.name}</span>
                <code className="text-xs text-gray-400">{m.slug}</code>
                {!m.is_enabled && <span className="badge text-xs">отключён</span>}
              </label>
            ))}
          </div>
        </Modal>
      )}

      {groupsUser && (
        <Modal title={`Доступ к кабинетам — ${groupsUser.username}`} onClose={() => setGroupsUser(null)}>
          <p className="text-xs text-gray-500 mb-3">
            {groupsUser.role === "teacher"
              ? "Преподаватель видит и управляет только отмеченными кабинетами. Если не отмечен ни один — он не видит ни одного хоста."
              : "Если ни один кабинет не отмечен — пользователь видит все хосты."}
          </p>
          <div className="space-y-2 max-h-[60vh] overflow-y-auto pr-1">
            {groups.length === 0 && <p className="text-gray-500 text-sm">Нет кабинетов</p>}
            {groups.map((g) => (
              <label key={g.group_id} className="flex items-center gap-3 p-3 rounded-[10px] border border-gray-200 dark:border-gray-700 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800">
                <input type="checkbox" checked={g.granted} onChange={(e) => setGroupAccess(g.group_id, e.target.checked)} className="w-4 h-4 accent-blue-600" />
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
