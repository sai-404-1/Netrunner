"use client";

import {useEffect, useMemo, useState} from "react";
import {useRouter} from "next/navigation";
import {apiGetClient, apiPostClient} from "@/lib/api-client";
import {readFileAsBase64} from "@/lib/utils";
import {useToast} from "@/components/Toast";
import {useAuth} from "@/components/AuthProvider";
import type {Group, Host, SshKey} from "@/lib/host-types";
import {HostList} from "./HostList";
import {AddHostModal} from "./modals/AddHostModal";
import {EditHostModal} from "./modals/EditHostModal";
import {ReprovisionModal} from "./modals/ReprovisionModal";
import {BulkReprovisionModal} from "./modals/BulkReprovisionModal";
import {GroupCreateModal} from "./modals/GroupCreateModal";
import {GroupEditModal} from "./modals/GroupEditModal";

export default function HostsPage() {
  const {user} = useAuth();
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
  const [reprovisionHost, setReprovisionHost] = useState<Host | null>(null);
  const [reprovisioning, setReprovisioning] = useState(false);
  const [newKeyFile, setNewKeyFile] = useState<File | null>(null);
  const [editKeyFile, setEditKeyFile] = useState<File | null>(null);
  const [createGroupOpen, setCreateGroupOpen] = useState(false);
  const [editGroup, setEditGroup] = useState<Group | null>(null);

  // Bulk selection
  const [selectionMode, setSelectionMode] = useState(false);
  const [addHostHidden, setAddHostHidden] = useState(true);
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
        const r = await apiPostClient("/api/hosts/check", {id});
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
  async function bulkReprovision(fd: FormData) {
    if (selectedIds.size === 0) return;
    setBulkLoading(true);
    let ok = 0, fail = 0;
    const password = fd.get("password") as string | null;
    const sshKeyId = fd.get("ssh_key_id") as string | null;
    for (const id of selectedIds) {
      try {
        const data: any = {id};
        if (password) data.password = password;
        if (sshKeyId) data.ssh_key_id = Number(sshKeyId);
        const r = await apiPostClient("/api/hosts/reprovision", data);
        if (r.is_active) ok++; else fail++;
      } catch {
        fail++;
      }
    }
    showToast(`Перепривязка: ${ok} успешно, ${fail} ошибок`);
    setBulkLoading(false);
    setBulkReprovisionOpen(false);
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
        await apiPostClient("/api/hosts/delete", {id});
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

  async function onCreateHost(fd: FormData, keyFile: File | null) {
    try {
      let sshKeyId: number | null = null;
      if (keyFile) {
        const fileData = await readFileAsBase64(keyFile);
        const key = await apiPostClient("/api/ssh-keys", {name: keyFile.name, file_data: fileData});
        sshKeyId = key.id;
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
        await apiPostClient("/api/groups/add-host", {group_id: groupId, host_id: host.id});
      }
      showToast("Хост добавлен");
      setAddHostHidden(true);
      await load();
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  async function onUpdateHost(fd: FormData, keyFile: File | null) {
    try {
      let sshKeyId: number | null = null;
      if (keyFile) {
        const fileData = await readFileAsBase64(keyFile);
        const key = await apiPostClient("/api/ssh-keys", {name: keyFile.name, file_data: fileData});
        sshKeyId = key.id;
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

  async function reprovision(fd: FormData) {
    if (!reprovisionHost) return;
    const password = (fd.get("password") as string) || null;
    const sshKeyId = (fd.get("ssh_key_id") as string) || null;
    setReprovisioning(true);
    try {
      const data: any = {id: reprovisionHost.id};
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

  async function deleteHost(host: Host) {
    if (!confirm(`Удалить хост #${host.id}?`)) return;
    try {
      await apiPostClient("/api/hosts/delete", {id: host.id});
      showToast("Хост удалён");
      await load();
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  async function createGroup(fd: FormData) {
    try {
      await apiPostClient("/api/groups", {name: fd.get("name"), description: fd.get("description") || null});
      showToast("Группа создана");
      setCreateGroupOpen(false);
      await load();
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  async function updateGroup(fd: FormData) {
    try {
      await apiPostClient("/api/groups/update", {
        id: Number(fd.get("id")),
        name: fd.get("name"),
        description: fd.get("description") || null
      });
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
      await apiPostClient("/api/groups/delete", {id});
      showToast("Группа удалена");
      await load();
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  return (
    <div className="space-y-6">
      <HostList
        onHosts={() => setHosts}
        hosts={hosts}
        filteredHosts={filteredHosts}
        groups={groups}
        search={search}
        groupFilter={groupFilter}
        checkingAll={checkingAll}
        selectionMode={selectionMode}
        selectedIds={selectedIds}
        onSearch={setSearch}
        onGroupFilter={setGroupFilter}
        onCheckAll={checkAll}
        onToggleSelectionMode={toggleSelectionMode}
        onToggleSelect={toggleSelect}
        onAddHost={() => setAddHostHidden((v) => !v)}
        onInfoHost={(h) => router.push(`/hosts/${h.id}`)}
        onEditGroup={setEditGroup}
        onDeleteGroup={deleteGroup}
        onBoardsChange={load}
      />

      {!addHostHidden && (
        <AddHostModal
          groups={groups}
          onClose={() => setAddHostHidden(true)}
          onSubmit={onCreateHost}
          onCreateGroup={() => setCreateGroupOpen(true)}
        />
      )}
      {editHost && (
        <EditHostModal
          host={editHost}
          groups={groups}
          keys={keys}
          onClose={() => setEditHost(null)}
          onSubmit={onUpdateHost}
        />
      )}
      {reprovisionHost && (
        <ReprovisionModal
          host={reprovisionHost}
          keys={keys}
          busy={reprovisioning}
          onClose={() => setReprovisionHost(null)}
          onSubmit={reprovision}
        />
      )}
      {bulkReprovisionOpen && (
        <BulkReprovisionModal
          count={selectedIds.size}
          keys={keys}
          busy={bulkLoading}
          onClose={() => setBulkReprovisionOpen(false)}
          onSubmit={bulkReprovision}
        />
      )}
      {createGroupOpen && (
        <GroupCreateModal
          onClose={() => setCreateGroupOpen(false)}
          onSubmit={createGroup}
        />
      )}
      {editGroup && (
        <GroupEditModal
          group={editGroup}
          onClose={() => setEditGroup(null)}
          onSubmit={updateGroup}
        />
      )}
    </div>
  );
}