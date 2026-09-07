"use client";

import { useEffect, useState } from "react";
import { apiGetClient, apiPostClient } from "@/lib/api-client";
import { useToast } from "@/components/Toast";
import { RefreshCw } from "lucide-react";
import type { ScheduledTask, Scenario, Host, Group } from "@/lib/schedule-types";
import TaskTable from "./TaskTable";
import TaskFormModal from "./TaskFormModal";

export default function ScheduledPage() {
  const showToast = useToast();
  const [tasks, setTasks] = useState<ScheduledTask[]>([]);
  const [tasksInactive, setInactiveTasks] = useState<ScheduledTask[]>([]);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [hosts, setHosts] = useState<Host[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [editTask, setEditTask] = useState<ScheduledTask | null>(null);
  const [listTab, setListTab] = useState<"active" | "inactive">("active");
  const [createOpen, setCreateOpen] = useState(false);

  async function load() {
    const [active, inactive, sc, h, g] = await Promise.all([
      apiGetClient("/api/schedule/active"),
      apiGetClient("/api/schedule/inactive"),
      apiGetClient("/api/scenarios"),
      apiGetClient("/api/hosts"),
      apiGetClient("/api/groups"),
    ]);
    setTasks(active || []);
    setInactiveTasks(inactive || []);
    setScenarios(sc || []);
    setHosts(h || []);
    setGroups(g || []);
  }

  useEffect(() => {
    load();
  }, []);

  async function handleSubmit(data: Record<string, unknown>, isEdit: boolean) {
    try {
      if (isEdit) {
        await apiPostClient("/api/schedule/update", { ...data, id: editTask?.id });
        showToast("Задача обновлена");
      } else {
        await apiPostClient("/api/schedule", data);
        showToast("Запланированная задача создана");
      }
      setEditTask(null);
      setCreateOpen(false);
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
      showToast("Информация обновлена");
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

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold">Планировщик</h2>
        <p className="text-gray-500">Создание и запуск запланированных задач</p>
      </div>

      <div className="panel">
        {/* Вкладки: Активные / Не активные */}
        <div className="flex items-center gap-1 mb-4 justify-between">
          <div className="flex items-center gap-1 border-b border-gray-200 dark:border-gray-700">
            <button
              onClick={() => setListTab("active")}
              className={`px-4 py-2 text-sm font-semibold border-b-2 -mb-px transition-colors ${listTab === "active" ? "border-blue-600 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700"
                }`}
            >
              Активные
            </button>
            <button
              onClick={() => setListTab("inactive")}
              className={`px-4 py-2 text-sm font-semibold border-b-2 -mb-px transition-colors ${listTab === "inactive" ? "border-blue-600 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700"
                }`}
            >
              Не активные
            </button>
          </div>
          <div className="flex gap-2">
            <button className="btn-secondary" onClick={tickScheduler} title="Проверить расписание">
              <RefreshCw size={16} />
            </button>
            <button className="btn" onClick={() => setCreateOpen(true)} title="Создать запланированную задачу">
              Запланировать
            </button>
          </div>
        </div>

        <TaskTable
          rows={listTab === "active" ? tasks : tasksInactive}
          scenarios={scenarios}
          hosts={hosts}
          groups={groups}
          onEdit={setEditTask}
          onDelete={deleteTask}
          onToggle={toggleEnabled}
        />
      </div>

      {editTask && (
        <TaskFormModal
          title="Редактировать задачу"
          task={editTask}
          scenarios={scenarios}
          hosts={hosts}
          groups={groups}
          onClose={() => setEditTask(null)}
          onSubmit={handleSubmit}
        />
      )}

      {createOpen && (
        <TaskFormModal
          title="Создать запланированную задачу"
          scenarios={scenarios}
          hosts={hosts}
          groups={groups}
          onClose={() => setCreateOpen(false)}
          onSubmit={handleSubmit}
        />
      )}
    </div>
  );
}
