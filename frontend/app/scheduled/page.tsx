"use client";

import { useEffect, useState } from "react";
import { apiGetClient, apiPostClient } from "@/lib/api-client";
import { formatDate, toLocalISO } from "@/lib/utils";
import { BooleanBadge } from "@/components/Badge";
import { DataTable } from "@/components/DataTable";
import { Modal } from "@/components/Modal";
import { useToast } from "@/components/Toast";
import { Pencil, Trash2, Settings } from "lucide-react";

interface Template {
  id: number;
  name: string;
  module_id: number;
}

interface Host {
  id: number;
  name: string;
}

interface Group {
  id: number;
  name: string;
}

interface ScheduledTask {
  id: number;
  name: string;
  template_id: number;
  target_type: "host" | "group";
  target_id: number;
  run_at: string;
  is_enabled: boolean;
}

export default function ScheduledPage() {
  const showToast = useToast();
  const [tasks, setTasks] = useState<ScheduledTask[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [hosts, setHosts] = useState<Host[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [editTask, setEditTask] = useState<ScheduledTask | null>(null);

  async function load() {
    const [t, te, h, g] = await Promise.all([
      apiGetClient("/api/scheduled"),
      apiGetClient("/api/task-templates"),
      apiGetClient("/api/hosts"),
      apiGetClient("/api/groups"),
    ]);
    setTasks(t || []);
    setTemplates(te || []);
    setHosts(h || []);
    setGroups(g || []);
  }

  useEffect(() => {
    load();
  }, []);

  async function onCreate(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    try {
      await apiPostClient("/api/schedule", {
        name: fd.get("name"),
        template_id: Number(fd.get("template_id")),
        target_type: fd.get("target_type"),
        target_id: Number(fd.get("target_id")),
        run_at: fd.get("run_at") ? toLocalISO(new Date(String(fd.get("run_at")))) : "",
      });
      showToast("Запланированная задача создана");
      e.currentTarget.reset();
      await load();
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  async function onUpdate(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    try {
      await apiPostClient("/api/schedule/update", {
        id: Number(fd.get("id")),
        name: fd.get("name"),
        template_id: Number(fd.get("template_id")),
        target_type: fd.get("target_type"),
        target_id: Number(fd.get("target_id")),
        run_at: fd.get("run_at") ? toLocalISO(new Date(String(fd.get("run_at")))) : "",
        is_enabled: fd.get("is_enabled") === "on",
      });
      showToast("Задача обновлена");
      setEditTask(null);
      await load();
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  async function deleteTask(id: number) {
    if (!confirm("Удалить запланированную задачу?")) return;
    try {
      await apiPostClient("/api/schedule/delete", { id });
      showToast("Задача удалена");
      await load();
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  async function tickScheduler() {
    try {
      await apiPostClient("/api/scheduler/tick", {});
      showToast("Планировщик проверен");
      await load();
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  async function toggleEnabled(task: ScheduledTask) {
    try {
      await apiPostClient("/api/schedule/update", { id: task.id, is_enabled: !task.is_enabled });
      showToast(!task.is_enabled ? "Задача активирована" : "Задача отключена");
      await load();
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  const targets = (type: "host" | "group") => (type === "host" ? hosts : groups);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold">Планировщик</h2>
        <p className="text-gray-500">Создание и запуск запланированных задач</p>
      </div>

      <div className="panel">
        <h3 className="font-semibold mb-4">Создать запланированную задачу</h3>
        <form onSubmit={onCreate} className="flex flex-wrap gap-4 items-end">
          <label className="label flex-1 min-w-[200px]">
            Название
            <input className="input" name="name" placeholder="Плановая инвентаризация" required />
          </label>
          <label className="label flex-1 min-w-[200px]">
            Шаблон
            <select className="input" name="template_id" required>
              {templates.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name} #{t.id}
                </option>
              ))}
            </select>
          </label>
          <label className="label flex-1 min-w-[140px]">
            Тип цели
            <select className="input" name="target_type" defaultValue="host">
              <option value="host">Хост</option>
              <option value="group">Группа</option>
            </select>
          </label>
          <label className="label flex-1 min-w-[200px]">
            Цель
            <select className="input" name="target_id" required>
              {hosts.map((h) => (
                <option key={h.id} value={h.id}>
                  {h.name} #{h.id}
                </option>
              ))}
            </select>
          </label>
          <label className="label flex-1 min-w-[200px]">
            Время запуска
            <input className="input" name="run_at" type="datetime-local" required />
          </label>
          <button className="btn" type="submit">
            Создать
          </button>
        </form>
      </div>

      <div className="panel">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold">Запланированные задачи</h3>
          <button className="btn-secondary" onClick={tickScheduler}>
            <Settings size={16} /> Прогнать планировщик
          </button>
        </div>
        <DataTable
          columns={[
            { title: "Название", key: "name" },
            { title: "Шаблон", render: (t) => templates.find((x) => x.id === t.template_id)?.name || t.template_id },
            {
              title: "Цель",
              render: (t) => {
                const target = targets(t.target_type).find((x) => x.id === t.target_id);
                return `${t.target_type === "host" ? "хост" : "группа"}:${target?.name || t.target_id}`;
              },
            },
            { title: "Запуск", render: (t) => formatDate(t.run_at) },
            {
              title: "Активна",
              render: (t) => (
                <label className="inline-flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={t.is_enabled} onChange={() => toggleEnabled(t)} className="w-5 h-5" />
                  <BooleanBadge value={t.is_enabled} />
                </label>
              ),
            },
            {
              title: "",
              render: (t) => (
                <div className="flex gap-2 justify-end">
                  <button className="btn-secondary p-2" onClick={() => setEditTask(t)} title="Редактировать">
                    <Pencil size={16} />
                  </button>
                  <button className="btn-secondary p-2 text-red-600" onClick={() => deleteTask(t.id)} title="Удалить">
                    <Trash2 size={16} />
                  </button>
                </div>
              ),
            },
          ]}
          rows={tasks}
        />
      </div>

      {editTask && (
        <Modal title="Редактирование задачи" onClose={() => setEditTask(null)}>
          <form onSubmit={onUpdate} className="grid gap-4">
            <input type="hidden" name="id" value={editTask.id} />
            <label className="label">
              Название
              <input className="input" name="name" defaultValue={editTask.name} required />
            </label>
            <label className="label">
              Шаблон
              <select className="input" name="template_id" defaultValue={editTask.template_id}>
                {templates.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name} #{t.id}
                  </option>
                ))}
              </select>
            </label>
            <label className="label">
              Тип цели
              <select className="input" name="target_type" defaultValue={editTask.target_type}>
                <option value="host">Хост</option>
                <option value="group">Группа</option>
              </select>
            </label>
            <label className="label">
              Цель
              <select className="input" name="target_id" defaultValue={editTask.target_id}>
                {targets(editTask.target_type).map((x) => (
                  <option key={x.id} value={x.id}>
                    {x.name} #{x.id}
                  </option>
                ))}
              </select>
            </label>
            <label className="label">
              Время запуска
              <input className="input" name="run_at" type="datetime-local" defaultValue={editTask.run_at ? editTask.run_at.slice(0, 16) : ""} required />
            </label>
            <label className="label inline-flex flex-row items-center gap-3 cursor-pointer">
              <input type="checkbox" name="is_enabled" defaultChecked={editTask.is_enabled} className="w-5 h-5" />
              <span>Активна</span>
            </label>
            <div className="flex gap-3">
              <button className="btn" type="submit">
                Сохранить
              </button>
              <button type="button" className="btn-secondary" onClick={() => setEditTask(null)}>
                Отмена
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
