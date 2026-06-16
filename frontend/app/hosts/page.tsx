"use client";

import { useEffect, useMemo, useState } from "react";
import { apiGetClient, apiPostClient } from "@/lib/api";
import { formatDate, readFileAsBase64 } from "@/lib/utils";
import { BooleanBadge } from "@/components/Badge";
import { DataTable } from "@/components/DataTable";
import { Modal } from "@/components/Modal";
import { useToast } from "@/components/Toast";
import { RefreshCw, Pencil, Trash2, Search, CheckCircle } from "lucide-react";

interface Host {
  id: number;
  name: string;
  username: string;
  address: string;
  port: number;
  is_active: boolean;
  last_seen?: string;
  group_id?: number;
  group_name?: string;
  ssh_key_id?: number;
  description?: string;
}

interface Group {
  id: number;
  name: string;
  kind: string;
  description?: string;
  hosts: (number | Host)[];
}

interface SshKey {
  id: number;
  name: string;
  key_type?: string;
  private_key_path?: string;
  public_key_path?: string;
  fingerprint?: string;
  public_key?: string;
  is_default?: boolean;
}

export default function HostsPage() {
  const showToast = useToast();
  const [hosts, setHosts] = useState<Host[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [keys, setKeys] = useState<SshKey[]>([]);
  const [search, setSearch] = useState("");
  const [groupFilter, setGroupFilter] = useState("");
  const [checkingAll, setCheckingAll] = useState(false);
  const [editHost, setEditHost] = useState<Host | null>(null);
  const [newKeyFile, setNewKeyFile] = useState<File | null>(null);
  const [editKeyFile, setEditKeyFile] = useState<File | null>(null);
  const [createGroupOpen, setCreateGroupOpen] = useState(false);
  const [editGroup, setEditGroup] = useState<Group | null>(null);

  async function load() {
    const [h, g, k] = await Promise.all([apiGetClient("/api/hosts"), apiGetClient("/api/groups"), apiGetClient("/api/ssh-keys")]);
    setHosts(h || []);
    setGroups(g || []);
    setKeys(k || []);
  }

  useEffect(() => {
    load();
  }, []);

  const filteredHosts = useMemo(() => {
    let rows = hosts;
    if (search) {
      const s = search.toLowerCase();
      rows = rows.filter((h) => `${h.name} ${h.address} ${h.username} ${h.description}`.toLowerCase().includes(s));
    }
    if (groupFilter === "none") {
      rows = rows.filter((h) => !h.group_id);
    } else if (groupFilter) {
      const group = groups.find((g) => String(g.id) === groupFilter);
      if (group) {
        const ids = group.hosts.map((h) => (typeof h === "number" ? h : h.id));
        rows = rows.filter((h) => ids.includes(h.id));
      }
    }
    return rows;
  }, [hosts, groups, search, groupFilter]);

  async function onCreateHost(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    let sshKeyId: number | null = null;
    if (newKeyFile) {
      const fileData = await readFileAsBase64(newKeyFile);
      const key = await apiPostClient("/api/ssh-keys", { name: newKeyFile.name, file_data: fileData });
      sshKeyId = key.id;
      setNewKeyFile(null);
    } else {
      sshKeyId = fd.get("ssh_key_id") ? Number(fd.get("ssh_key_id")) : null;
    }
    const data: any = {
      name: fd.get("name"),
      username: fd.get("username"),
      address: fd.get("address"),
      port: Number(fd.get("port") || 22),
      ssh_key_id: sshKeyId,
      description: fd.get("description") || null,
      password: fd.get("password") || null,
    };
    if (!data.password) delete data.password;
    const host = await apiPostClient("/api/hosts", data);
    const groupId = fd.get("group_id") ? Number(fd.get("group_id")) : null;
    if (groupId) {
      await apiPostClient("/api/groups/add-host", { group_id: groupId, host_id: host.id });
    }
    showToast("Хост добавлен");
    e.currentTarget.reset();
    await load();
  }

  async function onUpdateHost(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    let sshKeyId: number | null = null;
    if (editKeyFile) {
      const fileData = await readFileAsBase64(editKeyFile);
      const key = await apiPostClient("/api/ssh-keys", { name: editKeyFile.name, file_data: fileData });
      sshKeyId = key.id;
      setEditKeyFile(null);
    } else {
      sshKeyId = fd.get("ssh_key_id") ? Number(fd.get("ssh_key_id")) : null;
    }
    const data: any = {
      id: Number(fd.get("id")),
      name: fd.get("name"),
      username: fd.get("username"),
      address: fd.get("address"),
      port: Number(fd.get("port") || 22),
      ssh_key_id: sshKeyId,
      description: fd.get("description") || null,
      password: fd.get("password") || null,
      group_id: fd.get("group_id") ? Number(fd.get("group_id")) : null,
    };
    if (!data.password) delete data.password;
    await apiPostClient("/api/hosts/update", data);
    showToast("Хост обновлён");
    setEditHost(null);
    await load();
  }

  async function checkHost(id: number, el?: HTMLElement) {
    const icon = el?.querySelector("svg");
    icon?.classList.add("animate-spin");
    try {
      const result = await apiPostClient("/api/hosts/check", { id });
      showToast(`Хост ${result.host?.name}: ${result.host?.is_active ? "доступен" : "недоступен"}`);
      await load();
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      icon?.classList.remove("animate-spin");
    }
  }

  async function checkAll() {
    setCheckingAll(true);
    try {
      const result = await apiPostClient("/api/hosts/check-all", {});
      showToast(`Проверено: ${result.checked} хостов, доступно ${result.active}`);
      await load();
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setCheckingAll(false);
    }
  }

  async function deleteHost(id: number) {
    if (!confirm(`Удалить хост #${id}?`)) return;
    try {
      await apiPostClient("/api/hosts/delete", { id });
      showToast("Хост удалён");
      await load();
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  async function createGroup(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    try {
      await apiPostClient("/api/groups", { name: fd.get("name"), description: fd.get("description") || null });
      showToast("Группа создана");
      setCreateGroupOpen(false);
      e.currentTarget.reset();
      await load();
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  async function updateGroup(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    try {
      await apiPostClient("/api/groups/update", { id: Number(fd.get("id")), name: fd.get("name"), description: fd.get("description") || null });
      showToast("Группа обновлена");
      setEditGroup(null);
      await load();
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  async function deleteGroup(id: number) {
    const group = groups.find((g) => g.id === id);
    if (!confirm(`Удалить группу "${group?.name || id}"? Хосты в группе останутся без группы.`)) return;
    try {
      await apiPostClient("/api/groups/delete", { id });
      showToast("Группа удалена");
      await load();
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold">Хосты</h2>
        <p className="text-gray-500">Реестр управляемых узлов и добавление новых машин</p>
      </div>

      <div className="panel">
        <h3 className="font-semibold mb-4">Добавить хост</h3>
        <form onSubmit={onCreateHost} className="grid md:grid-cols-2 lg:grid-cols-4 gap-4 items-end">
          <label className="label">
            Имя хоста
            <input className="input" name="name" placeholder="fedora-vm" required />
          </label>
          <label className="label">
            Пользователь
            <input className="input" name="username" placeholder="admin" required />
          </label>
          <label className="label">
            IP-адрес
            <input className="input" name="address" placeholder="192.168.1.10" required />
          </label>
          <label className="label">
            Порт
            <input className="input" name="port" type="number" defaultValue={22} required />
          </label>
          <label className="label">
            Группа
            <select className="input" name="group_id">
              <option value="">Без группы</option>
              {groups.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.name}
                </option>
              ))}
            </select>
          </label>
          <label className="label">
            SSH-ключ
            <select className="input" name="ssh_key_id">
              <option value="">По умолчанию</option>
              {keys.map((k) => (
                <option key={k.id} value={k.id}>
                  {k.name} ({k.key_type || k.private_key_path})
                </option>
              ))}
            </select>
          </label>
          <label className="label">
            Новый SSH-ключ
            <input
              type="file"
              className="input py-1.5"
              onChange={(e) => setNewKeyFile(e.target.files?.[0] || null)}
            />
          </label>
          <label className="label">
            Пароль хоста
            <input className="input" name="password" type="password" placeholder="Для автокопирования SSH-ключа" />
          </label>
          <label className="label md:col-span-2 lg:col-span-4">
            Описание
            <textarea className="input" name="description" rows={3} />
          </label>
          <div className="flex gap-3 md:col-span-2 lg:col-span-4">
            <button className="btn" type="submit">
              Добавить
            </button>
            <button type="button" className="btn-secondary" onClick={() => setCreateGroupOpen(true)}>
              Создать группу
            </button>
          </div>
        </form>
      </div>

      <div className="panel">
        <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
          <h3 className="font-semibold">Зарегистрированные хосты</h3>
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                className="input pl-9"
                placeholder="Поиск по имени"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <select className="input" value={groupFilter} onChange={(e) => setGroupFilter(e.target.value)}>
              <option value="">Все группы</option>
              <option value="none">Без группы</option>
              {groups.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.name}
                </option>
              ))}
            </select>
            <button className="btn-secondary" onClick={checkAll} disabled={checkingAll}>
              <RefreshCw size={16} className={checkingAll ? "animate-spin" : ""} /> Проверить все
            </button>
          </div>
        </div>
        <DataTable
          columns={[
            { title: "Имя", key: "name" },
            { title: "Пользователь", key: "username" },
            { title: "IP-адрес", key: "address" },
            { title: "Порт", key: "port" },
            { title: "Активен", render: (h) => <BooleanBadge value={h.is_active} yes="Активен" no="Недоступен" /> },
            { title: "Был в сети", render: (h) => formatDate(h.last_seen) },
            { title: "Группа", render: (h) => h.group_name || "—" },
            { title: "Описание", render: (h) => h.description || "—" },
            {
              title: "",
              render: (h) => (
                <div className="flex gap-2 justify-end">
                  <button className="btn-secondary p-2" onClick={(e) => checkHost(h.id, e.currentTarget as HTMLElement)} title="Проверить доступность">
                    <RefreshCw size={16} />
                  </button>
                  <button className="btn-secondary p-2" onClick={() => setEditHost(h)} title="Редактировать">
                    <Pencil size={16} />
                  </button>
                  <button className="btn-secondary p-2 text-red-600" onClick={() => deleteHost(h.id)} title="Удалить">
                    <Trash2 size={16} />
                  </button>
                </div>
              ),
            },
          ]}
          rows={filteredHosts}
        />
      </div>

      <div className="panel">
        <h3 className="font-semibold mb-4">Группы</h3>
        <DataTable
          columns={[
            { title: "Название", key: "name" },
            { title: "Тип", key: "kind" },
            { title: "Описание", render: (g) => g.description || "—" },
            { title: "Хостов", render: (g) => g.hosts.length },
            {
              title: "",
              render: (g) => (
                <div className="flex gap-2 justify-end">
                  <button className="btn-secondary p-2" onClick={() => setEditGroup(g)} title="Редактировать">
                    <Pencil size={16} />
                  </button>
                  <button className="btn-secondary p-2 text-red-600" onClick={() => deleteGroup(g.id)} title="Удалить">
                    <Trash2 size={16} />
                  </button>
                </div>
              ),
            },
          ]}
          rows={groups}
        />
      </div>

      {editHost && (
        <Modal title="Редактирование хоста" onClose={() => setEditHost(null)}>
          <form onSubmit={onUpdateHost} className="grid md:grid-cols-2 gap-4">
            <input type="hidden" name="id" value={editHost.id} />
            <label className="label">
              Имя хоста
              <input className="input" name="name" defaultValue={editHost.name} required />
            </label>
            <label className="label">
              Пользователь
              <input className="input" name="username" defaultValue={editHost.username} required />
            </label>
            <label className="label">
              IP-адрес
              <input className="input" name="address" defaultValue={editHost.address} required />
            </label>
            <label className="label">
              Порт
              <input className="input" name="port" type="number" defaultValue={editHost.port} required />
            </label>
            <label className="label">
              Группа
              <select className="input" name="group_id" defaultValue={editHost.group_id || ""}>
                <option value="">Без группы</option>
                {groups.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="label">
              SSH-ключ
              <select className="input" name="ssh_key_id" defaultValue={editHost.ssh_key_id || ""}>
                <option value="">По умолчанию</option>
                {keys.map((k) => (
                  <option key={k.id} value={k.id}>
                    {k.name} ({k.key_type || k.private_key_path})
                  </option>
                ))}
              </select>
            </label>
            <label className="label">
              Новый SSH-ключ
              <input type="file" className="input py-1.5" onChange={(e) => setEditKeyFile(e.target.files?.[0] || null)} />
            </label>
            <label className="label">
              Пароль хоста
              <input className="input" name="password" type="password" placeholder="Для автокопирования SSH-ключа" />
            </label>
            <label className="label md:col-span-2">
              Описание
              <textarea className="input" name="description" rows={3} defaultValue={editHost.description || ""} />
            </label>
            <div className="flex gap-3 md:col-span-2">
              <button className="btn" type="submit">
                Сохранить
              </button>
              <button type="button" className="btn-secondary" onClick={() => setEditHost(null)}>
                Отмена
              </button>
            </div>
          </form>
        </Modal>
      )}

      {createGroupOpen && (
        <Modal title="Создать группу" onClose={() => setCreateGroupOpen(false)}>
          <form onSubmit={createGroup} className="grid gap-4">
            <label className="label">
              Название
              <input className="input" name="name" required />
            </label>
            <label className="label">
              Описание
              <textarea className="input" name="description" rows={3} />
            </label>
            <div className="flex gap-3">
              <button className="btn" type="submit">
                Создать
              </button>
              <button type="button" className="btn-secondary" onClick={() => setCreateGroupOpen(false)}>
                Отмена
              </button>
            </div>
          </form>
        </Modal>
      )}

      {editGroup && (
        <Modal title="Редактирование группы" onClose={() => setEditGroup(null)}>
          <form onSubmit={updateGroup} className="grid gap-4">
            <input type="hidden" name="id" value={editGroup.id} />
            <label className="label">
              Название
              <input className="input" name="name" defaultValue={editGroup.name} required />
            </label>
            <label className="label">
              Описание
              <textarea className="input" name="description" rows={3} defaultValue={editGroup.description || ""} />
            </label>
            <div className="flex gap-3">
              <button className="btn" type="submit">
                Сохранить
              </button>
              <button type="button" className="btn-secondary" onClick={() => setEditGroup(null)}>
                Отмена
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
