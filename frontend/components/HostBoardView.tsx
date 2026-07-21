"use client";

import { useState, useCallback, useEffect } from "react";
import { apiGetClient, apiPostClient } from "@/lib/api-client";
import { useToast } from "@/components/Toast";
import { BoardCanvas } from "@/components/BoardCanvas";
import { Modal } from "@/components/Modal";
import { useAuth } from "@/components/AuthProvider";
import { Plus, Save, Users } from "lucide-react";

interface Host {
  id: number;
  name: string;
  address: string;
  is_active: boolean | number;
}

interface Board {
  id: number;
  name: string;
  owner_user_id: number;
  width: number;
  height: number;
}

interface Placement {
  host_id: number;
  x: number;
  y: number;
  name: string;
  address: string;
  is_active: boolean | number;
}

interface AdminUser {
  id: number;
  username: string;
}

interface Props {
  hosts: Host[];
  onBoardsChange?: () => void;
}

export function HostBoardView({ hosts, onBoardsChange }: Props) {
  const { user } = useAuth();
  const showToast = useToast();
  const [boards, setBoards] = useState<Board[]>([]);
  const [activeBoardId, setActiveBoardId] = useState<number | null>(null);
  const [placements, setPlacements] = useState<Placement[]>([]);
  const [currentPlacements, setCurrentPlacements] = useState<Placement[]>([]);
  const [createOpen, setCreateOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [allUsers, setAllUsers] = useState<AdminUser[]>([]);
  const [filterUserId, setFilterUserId] = useState<number | null>(null);

  const loadBoards = useCallback(async () => {
    try {
      const query = user?.is_superuser && filterUserId ? `?user_id=${filterUserId}` : "";
      const data = await apiGetClient(`/api/boards${query}`);
      setBoards(data || []);
      if (data && data.length > 0 && !activeBoardId) {
        setActiveBoardId(data[0].id);
      }
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }, [showToast, filterUserId, activeBoardId, user]);

  useEffect(() => {
    loadBoards();
  }, [loadBoards]);

  useEffect(() => {
    if (user?.is_superuser) {
      apiGetClient("/api/admin/users")
        .then((data) => setAllUsers(data || []))
        .catch(() => {});
    }
  }, [user]);

  useEffect(() => {
    if (!activeBoardId) return;
    apiGetClient(`/api/boards/${activeBoardId}`)
      .then((data) => {
        if (data) setPlacements(data.placements || []);
      })
      .catch(() => {});
  }, [activeBoardId]);

  async function createBoard(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const fd = new FormData(form);
    try {
      const payload: any = {
        name: fd.get("name"),
        width: Number(fd.get("width") || 1600),
        height: Number(fd.get("height") || 900),
      };
      if (user?.is_superuser && fd.get("owner_user_id")) {
        payload.owner_user_id = Number(fd.get("owner_user_id"));
      }
      const board = await apiPostClient("/api/boards", payload);
      setBoards((prev) => [...prev, board]);
      setActiveBoardId(board.id);
      setCreateOpen(false);
      form.reset();
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  async function saveLayout() {
    if (!activeBoardId) return;
    setSaving(true);
    try {
      await apiPostClient(`/api/boards/${activeBoardId}/layout`, currentPlacements.map((p) => ({
        host_id: p.host_id,
        x: p.x,
        y: p.y,
      })));
      showToast("Расположение сохранено");
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setSaving(false);
    }
  }

  const handlePlacementsChange = useCallback((p: Placement[]) => {
    setCurrentPlacements(p);
  }, []);

  const activeBoard = boards.find((b) => b.id === activeBoardId) || null;

  return (
    <div className="flex flex-col h-full gap-3" style={{ minHeight: 0 }}>
      <div className="flex items-center gap-3 flex-wrap shrink-0">
        <select
          className="input w-48"
          value={activeBoardId ?? ""}
          onChange={(e) => setActiveBoardId(Number(e.target.value) || null)}
        >
          <option value="">— Выберите доску —</option>
          {boards.map((b) => (
            <option key={b.id} value={b.id}>
              {b.name}
            </option>
          ))}
        </select>

        <button className="btn-secondary flex items-center gap-2" onClick={() => setCreateOpen(true)}>
          <Plus size={16} />
          Новая доска
        </button>

        {activeBoard && (
          <button
            className="btn flex items-center gap-2 ml-auto"
            onClick={saveLayout}
            disabled={saving}
          >
            <Save size={16} />
            {saving ? "Сохранение..." : "Сохранить"}
          </button>
        )}

        {Boolean(user?.is_superuser) && allUsers.length > 0 && (
          <div className="flex items-center gap-2 ml-auto">
            <Users size={16} className="text-gray-400" />
            <select
              className="input w-40 text-sm"
              value={filterUserId ?? ""}
              onChange={(e) => {
                setFilterUserId(Number(e.target.value) || null);
                setActiveBoardId(null);
              }}
            >
              <option value="">Все пользователи</option>
              {allUsers.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.username}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      <div className="flex-1 min-h-0">
        {activeBoard ? (
          <BoardCanvas
            key={activeBoardId}
            board={activeBoard}
            availableHosts={hosts}
            initialPlacements={placements}
            onChange={handlePlacementsChange}
          />
        ) : (
          <div className="flex items-center justify-center h-64 text-gray-400 border rounded-xl bg-gray-50">
            Выберите доску или создайте новую
          </div>
        )}
      </div>

      {createOpen && (
        <Modal title="Новая доска" onClose={() => setCreateOpen(false)}>
          <form onSubmit={createBoard} className="space-y-4">
            <label className="label">
              Название
              <input className="input" name="name" required placeholder="Кабинет 301" />
            </label>
            <div className="grid grid-cols-2 gap-4">
              <label className="label">
                Ширина (px)
                <input className="input" name="width" type="number" defaultValue={1600} min={400} />
              </label>
              <label className="label">
                Высота (px)
                <input className="input" name="height" type="number" defaultValue={900} min={300} />
              </label>
            </div>
            {Boolean(user?.is_superuser) && allUsers.length > 0 && (
              <label className="label">
                Владелец
                <select className="input" name="owner_user_id">
                  <option value="">Текущий пользователь</option>
                  {allUsers.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.username}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <div className="flex gap-2 justify-end">
              <button type="button" className="btn-secondary" onClick={() => setCreateOpen(false)}>
                Отмена
              </button>
              <button type="submit" className="btn">
                Создать
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
