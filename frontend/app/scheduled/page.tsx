"use client";

import { useEffect, useState } from "react";
import { apiGetClient, apiPostClient } from "@/lib/api-client";
import { formatDate, toLocalISO } from "@/lib/utils";
import { Modal } from "@/components/Modal";
import { useToast } from "@/components/Toast";
import { Pencil, Trash2, Settings, Settings2, RefreshCw } from "lucide-react";
import type { ScheduledTask, Scenario, Host, Group } from "@/lib/schedule-types";
import EditTaskModal from "./EditTaskModal";
import TaskTable from "./TaskTable";
import CreateTaskModal from "./CreateTaskModal";

export default function ScheduledPage() {
  const showToast = useToast();
  const [tasks, setTasks] = useState<ScheduledTask[]>([]);
  const [tasksInactive, setInactiveTasks] = useState<ScheduledTask[]>([]);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [hosts, setHosts] = useState<Host[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [editTask, setEditTask] = useState<ScheduledTask | null>(null);
  const [listTab, setListTab] = useState<"active" | "inactive">("active");
  const [createTask, setCreateTask] = useState<true | false>(false);

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

  async function onCreate(fd: FormData) {
    try {
      await apiPostClient("/api/schedule", {
        name: fd.get("name"),
        scenario_id: Number(fd.get("scenario_id")),
        target_type: fd.get("target_type"),
        target_id: Number(fd.get("target_id")),
        run_at: fd.get("run_at") ? toLocalISO(new Date(String(fd.get("run_at")))) : "",
        wait_for_online: fd.get("wait_for_online") === "1",
      });
      showToast("Запланированная задача создана");
      setCreateTask(false); // закрыть модал вместо e.currentTarget.reset()
      await load();
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  async function onUpdate(fd: FormData) {
    try {
      await apiPostClient("/api/schedule/update", {
        id: Number(fd.get("id")),
        name: fd.get("name"),
        scenario_id: Number(fd.get("scenario_id")),
        target_type: fd.get("target_type"),
        target_id: Number(fd.get("target_id")),
        run_at: fd.get("run_at") ? toLocalISO(new Date(String(fd.get("run_at")))) : "",
        is_enabled: fd.get("is_enabled") === "on",
        wait_for_online: fd.get("wait_for_online") === "1",
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
          <div className="flex gap-5">
            <button className="btn-secondary" onClick={tickScheduler}>
              <RefreshCw size={16} />
            </button>
            <button className="btn" onClick={() => setCreateTask(!createTask)} title="Запланировать плановую задачу">Запланировать</button>
          </div>
        </div>
        {listTab == "inactive" && (
          <TaskTable
            rows={tasksInactive}
            scenarios={scenarios}
            hosts={hosts}
            groups={groups}
            onEdit={setEditTask}
            onDelete={deleteTask}
          />
        )}

        {listTab == "active" && (
          <TaskTable
            rows={tasks}
            scenarios={scenarios}
            hosts={hosts}
            groups={groups}
            onEdit={setEditTask}
            onDelete={deleteTask}
          />
        )}
      </div>

      {editTask && (
        <EditTaskModal
          task={editTask}
          scenarios={scenarios}
          hosts={hosts}
          groups={groups}
          onClose={() => setEditTask(null)}
          onSubmit={onUpdate}
        />
      )}

      {createTask && (
        <CreateTaskModal
          scenarios={scenarios}
          hosts={hosts}
          groups={groups}
          onClose={() => setCreateTask(false)}
          onCreate={onCreate}
        />
      )}
    </div>
  );
}
