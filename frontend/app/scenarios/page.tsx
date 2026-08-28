"use client";

import { useCallback, useEffect, useState } from "react";
import { apiGetClient, apiPostClient } from "@/lib/api-client";
import { useToast } from "@/components/Toast";
import { Play, Plus, X } from "lucide-react";
import { Scenario, Module, ScenarioRun } from "@/lib/scenario-types";
import ScenariosList from "./ScenariosList";
import RunExecution from "./RunExecution";
import RunsSidebar from "./RunsSidebar";
import { CreateScenarioModal } from "./modals/CreateScenarioModal";

export default function ScenariosPage() {
  const showToast = useToast();
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [modules, setModules] = useState<Module[]>([]);
  const [runs, setRuns] = useState<ScenarioRun[]>([]);
  const [loading, setLoading] = useState(true);

  // Мульти-выбор сценариев для запуска
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  // Create / edit modal
  const [createOpen, setCreateOpen] = useState(false);
  const [editScenario, setEditScenario] = useState<Scenario | null>(null);

  // Run form state (цель)
  const [runTargetType, setRunTargetType] = useState("host");
  const [runTargetId, setRunTargetId] = useState("");
  const [hosts, setHosts] = useState<{ id: number; name: string }[]>([]);
  const [groups, setGroups] = useState<{ id: number; name: string }[]>([]);
  // Запуски, открытые в блоке «Выполнение»: свои после старта или любой,
  // к которому подключились из списка справа.
  const [watchedIds, setWatchedIds] = useState<number[]>([]);
  const [activeRuns, setActiveRuns] = useState<ScenarioRun[]>([]);
  const [refreshingRuns, setRefreshingRuns] = useState(false);
  // Вкладка мобильной версии: на узком экране колонки не помещаются рядом.
  const [mobileTab, setMobileTab] = useState<"scenarios" | "runs">("scenarios");

  const loadData = useCallback(async () => {
    try {
      const [scenariosData, modulesData, hostsData, groupsData] = await Promise.all([
        apiGetClient("/api/scenarios"),
        apiGetClient("/api/modules"),
        apiGetClient("/api/hosts"),
        apiGetClient("/api/groups"),
      ]);
      setScenarios(scenariosData);
      setModules(modulesData.filter((m: Module) => m.supports_task_runner));
      setHosts(hostsData || []);
      setGroups(groupsData || []);
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  const loadRuns = useCallback(async () => {
    setRefreshingRuns(true);
    try {
      const runsData = await apiGetClient("/api/scenarios/runs?limit=50");
      setRuns(runsData);
    } catch {
      // silent
    } finally {
      setRefreshingRuns(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    loadRuns();
  }, [loadData, loadRuns]);

  // Опрос открытых запусков: тикает, пока среди них есть незавершённые.
  // Подключение к чужому/старому запуску — тот же путь, просто другой id.
  useEffect(() => {
    if (watchedIds.length === 0) {
      setActiveRuns([]);
      return;
    }
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    async function tick() {
      try {
        const data: ScenarioRun[] = await Promise.all(
          watchedIds.map((id) => apiGetClient(`/api/scenarios/runs/${id}`)),
        );
        if (stopped) return;
        setActiveRuns(data);
        if (data.some((r) => r.status === "running" || r.status === "pending")) {
          timer = setTimeout(tick, 1500);
        } else {
          loadRuns();
          loadData();
        }
      } catch {
        if (!stopped) timer = setTimeout(tick, 3000);
      }
    }

    tick();
    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
    };
  }, [watchedIds, loadRuns, loadData]);

  // Список справа обновляем и сам по себе — чтобы чужие запуски появлялись
  // в «Выполняются сейчас» без перезагрузки страницы.
  useEffect(() => {
    const timer = setInterval(loadRuns, 5000);
    return () => clearInterval(timer);
  }, [loadRuns]);

  const toggleSelect = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const handleRun = async (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedIds.size === 0) { showToast("Выберите хотя бы один сценарий", "error"); return; }
    if (!runTargetId) { showToast("Выберите цель", "error"); return; }
    setActiveRuns([]);
    try {
      const result = await apiPostClient("/api/scenarios/run", {
        scenario_ids: [...selectedIds],
        target_type: runTargetType,
        target_id: parseInt(runTargetId),
      });
      showToast("Сценарии запущены");
      setWatchedIds(result.run_ids || [result.run_id]);
      setMobileTab("scenarios");
    } catch (err: any) {
      showToast(err.message, "error");
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await apiPostClient("/api/scenarios/delete", { id });
      showToast("Сценарий удалён");
      setEditScenario(null);
      setSelectedIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
      loadData();
    } catch (err: any) {
      showToast(err.message, "error");
    }
  };

  // Порядок вставки в Set = порядок кликов пользователя. Строим панель
  // «Будут выполнены» в этом же порядке, чтобы визуал совпадал с реальной
  // очерёдностью запуска (иначе панель показывала бы сортировку по id).
  const selectedScenarios = [...selectedIds]
    .map((id) => scenarios.find((s) => s.id === id))
    .filter((s): s is Scenario => Boolean(s));

  const runningCount = runs.filter((r) => r.status === "running" || r.status === "pending").length;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold">Сценарии</h2>
        <p className="text-gray-500">Многошаговые сценарии для автоматизации действий на хостах</p>
      </div>

      {/* Вкладки — только на узких экранах, на широких обе колонки видны сразу */}
      <div className="flex gap-1 border-b dark:border-gray-700 lg:hidden">
        {([
          ["scenarios", "Сценарии"],
          ["runs", runningCount > 0 ? `Запуски (${runningCount})` : "Запуски"],
        ] as const).map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setMobileTab(key)}
            className={`px-4 py-2 text-sm font-semibold rounded-t-md border-b-2 -mb-px transition-colors ${
              mobileTab === key
                ? "border-blue-500 text-blue-600 dark:text-blue-400"
                : "border-transparent text-gray-500"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="grid lg:grid-cols-[minmax(0,1fr)_22rem] gap-6 items-start">
        <div className={`space-y-6 ${mobileTab === "scenarios" ? "" : "hidden"} lg:block`}>
        {/* Run form */}
        <div className="panel">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold">Запустить сценарий</h3>
            <button type="button" className="btn" onClick={() => setCreateOpen(true)}>
              <Plus size={16} /> Создать сценарий
            </button>
          </div>

          {/* Выбранные сценарии */}
          <div className="mb-3">
            {selectedScenarios.length === 0 ? (
              <p className="text-sm text-gray-500">Выберите сценарии ниже — они выполнятся по очереди.</p>
            ) : (
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm text-gray-500">Будут выполнены:</span>
                {selectedScenarios.map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => toggleSelect(s.id)}
                    title="Убрать из выбора"
                    className="group inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 text-sm hover:bg-red-50 hover:border-red-300 dark:hover:bg-red-950/40 dark:hover:border-red-700 transition-colors"
                  >
                    {s.name}
                    <X size={14} className="text-gray-400 group-hover:text-red-500 shrink-0" />
                  </button>
                ))}
              </div>
            )}
          </div>

          <form onSubmit={handleRun} className="space-y-3">
            <div className="grid md:grid-cols-2 gap-4 items-end">
              <label className="label">
                Тип цели
                <select className="input" value={runTargetType} onChange={(e) => { setRunTargetType(e.target.value); setRunTargetId(""); }}>
                  <option value="host">Хост</option>
                  <option value="group">Группа</option>
                </select>
              </label>
              <label className="label">
                Цель
                <select className="input" value={runTargetId} onChange={(e) => setRunTargetId(e.target.value)}>
                  <option value="">Выберите цель</option>
                  {(runTargetType === "host" ? hosts : groups).map((t) => (
                    <option key={t.id} value={t.id}>{t.name} #{t.id}</option>
                  ))}
                </select>
              </label>
            </div>
            <button className="btn" type="submit" disabled={selectedIds.size === 0}>
              <Play size={16} /> Запустить
            </button>
          </form>
        </div>

        {/* Живое выполнение: вкладка на каждый компьютер, внутри — его очередь сценариев */}
        <RunExecution
          runs={activeRuns}
          scenarios={scenarios}
          modules={modules}
          onClose={() => setWatchedIds([])}
        />

        {/* Scenario list — карточки: клик выбирает (мульти-выбор), карандаш редактирует */}
        <ScenariosList
          scenarios={scenarios}
          loading={loading}
          selectedIds={selectedIds}
          onToggle={toggleSelect}
          onEdit={setEditScenario}
        />
        </div>

        {/* Правая колонка: текущие запуски сверху, под ними история */}
        <aside className={`${mobileTab === "runs" ? "" : "hidden"} lg:block lg:sticky lg:top-4`}>
          <RunsSidebar
            runs={runs}
            watchedIds={watchedIds}
            refreshing={refreshingRuns}
            onRefresh={loadRuns}
            onWatch={(id) => {
              setWatchedIds([id]);
              setMobileTab("scenarios");
            }}
          />
        </aside>
      </div>

      {createOpen && (
        <CreateScenarioModal
          modules={modules}
          onClose={() => setCreateOpen(false)}
          onSaved={loadData}
        />
      )}
      {editScenario && (
        <CreateScenarioModal
          modules={modules}
          scenario={editScenario}
          onClose={() => setEditScenario(null)}
          onSaved={loadData}
          onDelete={() => handleDelete(editScenario.id)}
        />
      )}
    </div>
  );
}
