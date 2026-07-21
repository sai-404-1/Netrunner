"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { apiGetClient, apiPostClient } from "@/lib/api-client";
import { formatDate, readFileAsBase64 } from "@/lib/utils";
import { DataTable } from "@/components/DataTable";
import { Modal } from "@/components/Modal";
import { useToast } from "@/components/Toast";
import { RefreshCw, Pencil, Trash2, Search, CheckCircle, List, LayoutGrid, KeyRound, CheckSquare, Play, Info, TerminalSquare, ChevronLeft } from "lucide-react";
import { HostBoardView } from "@/components/HostBoardView";
import { useAuth } from "@/components/AuthProvider";

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
  const { user } = useAuth();
  const router = useRouter();
  const isTeacher = user?.role === "teacher" && !user?.is_superuser;
  const showToast = useToast();
  const [hosts, setHosts] = useState<Host[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [keys, setKeys] = useState<SshKey[]>([]);
  const [search, setSearch] = useState("");
  const [groupFilter, setGroupFilter] = useState("");
  const [checkingAll, setCheckingAll] = useState(false);
  const [editHost, setEditHost] = useState<Host | null>(null);
  const [infoHost, setInfoHost] = useState<Host | null>(null);
  const [reprovisionHost, setReprovisionHost] = useState<Host | null>(null);
  const [reprovisioning, setReprovisioning] = useState(false);
  const [newKeyFile, setNewKeyFile] = useState<File | null>(null);
  const [editKeyFile, setEditKeyFile] = useState<File | null>(null);
  const [createGroupOpen, setCreateGroupOpen] = useState(false);
  const [editGroup, setEditGroup] = useState<Group | null>(null);
  const [viewMode, setViewMode] = useState<"list" | "board">("list");
  const [listTab, setListTab] = useState<"hosts" | "groups">("hosts");

  // Bulk selection
  const [selectionMode, setSelectionMode] = useState(false);
  const [addHostCollapsed, setAddHostCollapsed] = useState(true);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [bulkLoading, setBulkLoading] = useState(false);
  const [bulkReprovisionOpen, setBulkReprovisionOpen] = useState(false);
  const [bulkPassword, setBulkPassword] = useState("");
  const [bulkSshKeyId, setBulkSshKeyId] = useState("");

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
    // Онлайн-хосты — сначала, остальные — после (порядок внутри каждой группы
    // сохраняется, Array.sort в современных движках стабилен).
    return [...rows].sort((a, b) => Number(b.is_active) - Number(a.is_active));
  }, [hosts, groups, search, groupFilter]);

  const allSelected = filteredHosts.length > 0 && filteredHosts.every((h) => selectedIds.has(h.id));
  const someSelected = selectedIds.size > 0;

  function toggleSelect(id: number) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleSelectAll() {
    if (allSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filteredHosts.map((h) => h.id)));
    }
  }

  function clearSelection() {
    setSelectedIds(new Set());
  }

  function toggleSelectionMode() {
    setSelectionMode((v) => {
      if (v) clearSelection();
      return !v;
    });
  }

  function exitSelectionMode() {
    clearSelection();
    setSelectionMode(false);
  }

  // Bulk check
  async function bulkCheck() {
    if (selectedIds.size === 0) return;
    setBulkLoading(true);
    let ok = 0, fail = 0;
    for (const id of selectedIds) {
      try {
        const r = await apiPostClient("/api/hosts/check", { id });
        if (r.host?.is_active) ok++; else fail++;
      } catch {
        fail++;
      }
    }
    showToast(`Проверено: ${ok} доступно, ${fail} недоступно`);
    setBulkLoading(false);
    clearSelection();
    await load();
  }

  // Bulk reprovision
  async function bulkReprovision() {
    if (selectedIds.size === 0) return;
    setBulkLoading(true);
    let ok = 0, fail = 0;
    for (const id of selectedIds) {
      try {
        const data: any = { id };
        if (bulkPassword) data.password = bulkPassword;
        if (bulkSshKeyId) data.ssh_key_id = Number(bulkSshKeyId);
        const r = await apiPostClient("/api/hosts/reprovision", data);
        if (r.is_active) ok++; else fail++;
      } catch {
        fail++;
      }
    }
    showToast(`Перепривязка: ${ok} успешно, ${fail} ошибок`);
    setBulkLoading(false);
    setBulkReprovisionOpen(false);
    setBulkPassword("");
    setBulkSshKeyId("");
    clearSelection();
    await load();
  }

  // Bulk delete
  async function bulkDelete() {
    if (selectedIds.size === 0) return;
    const msg = selectedIds.size === 1
      ? `Удалить хост?`
      : `Удалить ${selectedIds.size} хостов?`;
    if (!confirm(msg)) return;
    setBulkLoading(true);
    let ok = 0, fail = 0;
    for (const id of selectedIds) {
      try {
        await apiPostClient("/api/hosts/delete", { id });
        ok++;
      } catch {
        fail++;
      }
    }
    showToast(`Удалено: ${ok}, ошибок: ${fail}`);
    setBulkLoading(false);
    clearSelection();
    await load();
  }

  async function checkHost(id: number) {
    try {
      const result = await apiPostClient("/api/hosts/check", { id });
      showToast(`Хост ${result.host?.name}: ${result.host?.is_active ? "доступен" : "недоступен"}`);
      await load();
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  // ... existing functions unchanged
  async function onCreateHost(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const fd = new FormData(form);
    try {
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
      form.reset();
      await load();
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  async function onUpdateHost(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    try {
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
    } catch (err: any) {
      showToast(err.message, "error");
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

  async function reprovision(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!reprovisionHost) return;
    const fd = new FormData(e.currentTarget);
    const password = (fd.get("password") as string) || null;
    const sshKeyId = (fd.get("ssh_key_id") as string) || null;
    setReprovisioning(true);
    try {
      const data: any = { id: reprovisionHost.id };
      if (password) data.password = password;
      if (sshKeyId) data.ssh_key_id = Number(sshKeyId);
      const result = await apiPostClient("/api/hosts/reprovision", data);
      showToast(`Ключ заново привязан к ${result.host?.name}: ${result.is_active ? "хост доступен" : "хост недоступен"}`);
      setReprovisionHost(null);
      await load();
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setReprovisioning(false);
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
    const form = e.currentTarget;
    const fd = new FormData(form);
    try {
      await apiPostClient("/api/groups", { name: fd.get("name"), description: fd.get("description") || null });
      showToast("Группа создана");
      setCreateGroupOpen(false);
      form.reset();
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
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold">Хосты</h2>
          <p className="text-gray-500">Реестр управляемых узлов и добавление новых машин</p>
        </div>
        <div className="flex items-center border rounded-lg overflow-hidden shrink-0">
          <button
            className={`flex items-center gap-1.5 px-3 py-2 text-sm ${viewMode === "list" ? "bg-blue-600 text-white" : "text-gray-600 hover:bg-gray-100"}`}
            onClick={() => setViewMode("list")}
          >
            <List size={15} />
            Список
          </button>
          <button
            className={`flex items-center gap-1.5 px-3 py-2 text-sm ${viewMode === "board" ? "bg-blue-600 text-white" : "text-gray-600 hover:bg-gray-100"}`}
            onClick={() => setViewMode("board")}
          >
            <LayoutGrid size={15} />
            Доска
          </button>
        </div>
      </div>

      {viewMode === "board" && (
        <div style={{ height: "calc(100vh - 180px)" }}>
          <HostBoardView hosts={hosts} onBoardsChange={load} />
        </div>
      )}

      {viewMode === "list" && (
      <>
      {!isTeacher && <div className="panel">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold">Добавить хост</h3>
          <button
            type="button"
            className="btn-secondary p-1.5"
            onClick={() => setAddHostCollapsed((v) => !v)}
            title={addHostCollapsed ? "Развернуть" : "Свернуть"}
          >
            <ChevronLeft size={16} className={`transition-transform duration-200 ${addHostCollapsed ? "" : "rotate-180"}`} />
          </button>
        </div>
        {!addHostCollapsed && (
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
                <option key={g.id} value={g.id}>{g.name}</option>
              ))}
            </select>
          </label>
          <label className="label">
            SSH-ключ
            <select className="input" name="ssh_key_id">
              <option value="">По умолчанию</option>
              {keys.map((k) => (
                <option key={k.id} value={k.id}>{k.name} ({k.key_type || k.private_key_path})</option>
              ))}
            </select>
          </label>
          <label className="label">
            Новый SSH-ключ
            <input type="file" className="input py-1.5" onChange={(e) => setNewKeyFile(e.target.files?.[0] || null)} />
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
            <button className="btn" type="submit">Добавить</button>
            <button type="button" className="btn-secondary" onClick={() => setCreateGroupOpen(true)}>Создать группу</button>
          </div>
        </form>
        )}
      </div>}

      <div className="panel">
        {/* Вкладки: Хосты / Группы */}
        <div className="flex items-center gap-1 border-b border-gray-200 dark:border-gray-700 mb-4">
          <button
            onClick={() => setListTab("hosts")}
            className={`px-4 py-2 text-sm font-semibold border-b-2 -mb-px transition-colors ${
              listTab === "hosts" ? "border-blue-600 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            Хосты
          </button>
          <button
            onClick={() => setListTab("groups")}
            className={`px-4 py-2 text-sm font-semibold border-b-2 -mb-px transition-colors ${
              listTab === "groups" ? "border-blue-600 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            Группы
          </button>
        </div>

        {listTab === "hosts" && (
        <>
        {/* Панель действий: выбор, поиск, фильтр, проверка — строкой */}
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <button className={selectionMode ? "btn" : "btn-secondary"} onClick={toggleSelectionMode}>
            <CheckSquare size={16} /> Выбрать
          </button>
          <div className="relative">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input className="input pl-9" placeholder="Поиск по имени" value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <select className="input w-auto" value={groupFilter} onChange={(e) => setGroupFilter(e.target.value)}>
            <option value="">Все группы</option>
            <option value="none">Без группы</option>
            {groups.map((g) => (<option key={g.id} value={g.id}>{g.name}</option>))}
          </select>
          <button className="btn-secondary" onClick={checkAll} disabled={checkingAll}>
            <RefreshCw size={16} className={checkingAll ? "animate-spin" : ""} /> Проверить все
          </button>
        </div>

        {/* Bulk actions toolbar — видна пока активен режим выбора (кнопка «Выбрать») */}
        {selectionMode && (
          <div className="flex flex-wrap items-center gap-2 mb-4 p-3 bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 rounded-xl">
            <span className="w-full sm:w-auto text-sm font-semibold text-blue-800 dark:text-blue-300 mr-2">
              <CheckSquare size={16} className="inline mr-1" />
              Выбрано: {selectedIds.size}
            </span>
            <button className="btn-secondary py-1.5 px-3 text-sm" onClick={bulkCheck} disabled={bulkLoading || !someSelected}>
              <RefreshCw size={14} className={bulkLoading ? "animate-spin" : ""} /> Проверить
            </button>
            <button className="btn-secondary py-1.5 px-3 text-sm" onClick={() => setBulkReprovisionOpen(true)} disabled={bulkLoading || !someSelected}>
              <KeyRound size={14} /> Привязать ключ
            </button>
            <button className="btn-danger py-1.5 px-3 text-sm" onClick={bulkDelete} disabled={bulkLoading || !someSelected}>
              <Trash2 size={14} /> Удалить
            </button>
            <button className="btn-secondary py-1.5 px-3 text-sm sm:ml-auto" onClick={toggleSelectAll}>
              {allSelected ? "Снять все" : "Выбрать все"}
            </button>
            <button className="btn-secondary py-1.5 px-3 text-sm" onClick={exitSelectionMode}>
              Отменить
            </button>
          </div>
        )}

        {/* Сетка хостов: 1 колонка на телефоне, 2-3 на широких экранах.
            В режиме выбора клик по карточке переключает выделение — рамка
            утолщается (анимированно) и меняет цвет у выбранных карточек. */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {filteredHosts.length === 0 && (
            <div className="col-span-full text-center text-gray-500 dark:text-gray-400 py-8">Нет хостов</div>
          )}
          {filteredHosts.map((h) => {
            const selected = selectedIds.has(h.id);
            return (
              <div
                key={h.id}
                onClick={() => selectionMode && toggleSelect(h.id)}
                className={`flex items-center gap-3 rounded-2xl bg-white dark:bg-gray-800 p-4 transition-all duration-200 ${
                  selectionMode
                    ? `cursor-pointer border-4 ${selected ? "border-blue-600" : "border-gray-300 dark:border-gray-600 hover:border-blue-300 dark:hover:border-blue-700"}`
                    : "border-2 border-gray-200 dark:border-gray-700"
                }`}
              >
                <span
                  className={`w-2.5 h-2.5 rounded-full shrink-0 ${h.is_active ? "bg-green-500" : "bg-gray-400"}`}
                  title={h.is_active ? "Активен" : "Недоступен"}
                />
                <div className="min-w-0 flex-1">
                  <div className="font-semibold truncate">{h.name}</div>
                  <div className="text-sm text-gray-500 dark:text-gray-400 truncate">{h.address}</div>
                </div>
                <button
                  className="btn-secondary p-1.5 shrink-0"
                  onClick={(e) => { e.stopPropagation(); setInfoHost(h); }}
                  title="Информация"
                >
                  <Info size={15} />
                </button>
              </div>
            );
          })}
        </div>
        </>
        )}

        {listTab === "groups" && (
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
        )}
      </div>
      </>
      )}

      {infoHost && (
        <Modal title={infoHost.name} onClose={() => setInfoHost(null)}>
          <div className="grid gap-4">
            <div className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
              <div>
                <div className="text-gray-500">Пользователь</div>
                <div className="font-medium">{infoHost.username}</div>
              </div>
              <div>
                <div className="text-gray-500">Порт</div>
                <div className="font-medium">{infoHost.port}</div>
              </div>
              <div>
                <div className="text-gray-500">Был в сети</div>
                <div className="font-medium">{formatDate(infoHost.last_seen) || "—"}</div>
              </div>
              <div>
                <div className="text-gray-500">Группа</div>
                <div className="font-medium">{infoHost.group_name || "—"}</div>
              </div>
              <div className="col-span-2">
                <div className="text-gray-500">Описание</div>
                <div className="font-medium">{infoHost.description || "—"}</div>
              </div>
            </div>
            <div className="flex flex-wrap gap-2 pt-2 border-t dark:border-gray-700">
              <button className="btn-secondary" onClick={() => checkHost(infoHost.id)}>
                <RefreshCw size={15} /> Проверить
              </button>
              {Boolean(user?.is_superuser) && (
                <button className="btn-secondary" onClick={() => router.push(`/terminal?host=${infoHost.id}`)}>
                  <TerminalSquare size={15} /> Терминал
                </button>
              )}
              <button className="btn-secondary" onClick={() => { setInfoHost(null); setReprovisionHost(infoHost); }}>
                <KeyRound size={15} /> Перепривязать ключ
              </button>
              <button className="btn-secondary" onClick={() => { setInfoHost(null); setEditHost(infoHost); }}>
                <Pencil size={15} /> Редактировать
              </button>
              <button className="btn-danger" onClick={() => { setInfoHost(null); deleteHost(infoHost.id); }}>
                <Trash2 size={15} /> Удалить
              </button>
            </div>
          </div>
        </Modal>
      )}

      {editHost && (
        <Modal title="Редактирование хоста" onClose={() => setEditHost(null)}>
          <form onSubmit={onUpdateHost} className="grid md:grid-cols-2 gap-4">
            <input type="hidden" name="id" value={editHost.id} />
            <label className="label">Имя хоста<input className="input" name="name" defaultValue={editHost.name} required /></label>
            <label className="label">Пользователь<input className="input" name="username" defaultValue={editHost.username} required /></label>
            <label className="label">IP-адрес<input className="input" name="address" defaultValue={editHost.address} required /></label>
            <label className="label">Порт<input className="input" name="port" type="number" defaultValue={editHost.port} required /></label>
            <label className="label">Группа<select className="input" name="group_id" defaultValue={editHost.group_id || ""}>
              <option value="">Без группы</option>
              {groups.map((g) => (<option key={g.id} value={g.id}>{g.name}</option>))}
            </select></label>
            <label className="label">SSH-ключ<select className="input" name="ssh_key_id" defaultValue={editHost.ssh_key_id || ""}>
              <option value="">По умолчанию</option>
              {keys.map((k) => (<option key={k.id} value={k.id}>{k.name}</option>))}
            </select></label>
            <label className="label">Новый SSH-ключ<input type="file" className="input py-1.5" onChange={(e) => setEditKeyFile(e.target.files?.[0] || null)} /></label>
            <label className="label">Пароль хоста<input className="input" name="password" type="password" /></label>
            <label className="label md:col-span-2">Описание<textarea className="input" name="description" rows={3} defaultValue={editHost.description || ""} /></label>
            <div className="flex gap-3 md:col-span-2">
              <button className="btn" type="submit">Сохранить</button>
              <button type="button" className="btn-secondary" onClick={() => setEditHost(null)}>Отмена</button>
            </div>
          </form>
        </Modal>
      )}

      {reprovisionHost && (
        <Modal title="Перепривязка SSH-ключа" onClose={() => setReprovisionHost(null)}>
          <form onSubmit={reprovision} className="grid gap-4">
            <p className="text-sm text-gray-500">Заново скопирует SSH-ключ на хост <b>{reprovisionHost.name}</b> ({reprovisionHost.username}@{reprovisionHost.address}).</p>
            <label className="label">
              SSH-ключ
              <select className="input" name="ssh_key_id" defaultValue={reprovisionHost.ssh_key_id || ""}>
                <option value="">По умолчанию</option>
                {keys.map((k) => (<option key={k.id} value={k.id}>{k.name}</option>))}
              </select>
            </label>
            <label className="label">Пароль хоста<input className="input" name="password" type="password" placeholder="Оставьте пустым, чтобы использовать сохранённый" /></label>
            <div className="flex gap-3">
              <button className="btn" type="submit" disabled={reprovisioning}>{reprovisioning ? "Привязка…" : "Привязать ключ"}</button>
              <button type="button" className="btn-secondary" onClick={() => setReprovisionHost(null)}>Отмена</button>
            </div>
          </form>
        </Modal>
      )}

      {/* Bulk reprovision modal */}
      {bulkReprovisionOpen && (
        <Modal title="Массовая перепривязка SSH-ключа" onClose={() => setBulkReprovisionOpen(false)}>
          <div className="grid gap-4">
            <p className="text-sm text-gray-500">
              Перепривязать SSH-ключ для <b>{selectedIds.size}</b> хостов.
            </p>
            <label className="label">
              SSH-ключ
              <select className="input" value={bulkSshKeyId} onChange={(e) => setBulkSshKeyId(e.target.value)}>
                <option value="">Оставить текущий ключ каждого хоста</option>
                {keys.map((k) => (<option key={k.id} value={k.id}>{k.name}</option>))}
              </select>
            </label>
            <label className="label">Пароль хоста<input className="input" type="password" value={bulkPassword} onChange={(e) => setBulkPassword(e.target.value)} placeholder="Для всех выбранных хостов" /></label>
            <div className="flex gap-3">
              <button className="btn" onClick={bulkReprovision} disabled={bulkLoading}>
                {bulkLoading ? "Привязка…" : "Привязать для всех"}
              </button>
              <button type="button" className="btn-secondary" onClick={() => setBulkReprovisionOpen(false)}>Отмена</button>
            </div>
          </div>
        </Modal>
      )}

      {createGroupOpen && (
        <Modal title="Создать группу" onClose={() => setCreateGroupOpen(false)}>
          <form onSubmit={createGroup} className="grid gap-4">
            <label className="label">Название<input className="input" name="name" required /></label>
            <label className="label">Описание<textarea className="input" name="description" rows={3} /></label>
            <div className="flex gap-3">
              <button className="btn" type="submit">Создать</button>
              <button type="button" className="btn-secondary" onClick={() => setCreateGroupOpen(false)}>Отмена</button>
            </div>
          </form>
        </Modal>
      )}

      {editGroup && (
        <Modal title="Редактирование группы" onClose={() => setEditGroup(null)}>
          <form onSubmit={updateGroup} className="grid gap-4">
            <input type="hidden" name="id" value={editGroup.id} />
            <label className="label">Название<input className="input" name="name" defaultValue={editGroup.name} required /></label>
            <label className="label">Описание<textarea className="input" name="description" rows={3} defaultValue={editGroup.description || ""} /></label>
            <div className="flex gap-3">
              <button className="btn" type="submit">Сохранить</button>
              <button type="button" className="btn-secondary" onClick={() => setEditGroup(null)}>Отмена</button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
