"use client";

import { useCallback, useEffect, useState } from "react";
import { apiGetClient, apiPostClient } from "@/lib/api-client";
import { useToast } from "@/components/Toast";
import { ChevronDown, Play, Plus, X } from "lucide-react";
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

  // Цель запуска — мультивыбор: набор кабинетов (групп целиком) и набор
  // отдельных компьютеров. Сервер раскрывает смесь в общий список хостов.
  const [runGroups, setRunGroups] = useState<Set<number>>(new Set());
  const [runHosts, setRunHosts] = useState<Set<number>>(new Set());
  const [targetsOpen, setTargetsOpen] = useState(false);
  const [hosts, setHosts] = useState<{ id: number; name: string; address?: string }[]>([]);
  const [groups, setGroups] = useState<{ id: number; name: string; hosts?: { id: number }[] }[]>([]);
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

  /** Переключает id в наборе целей (кабинеты/компьютеры выбираются независимо). */
  const toggleIn = (set: Set<number>, apply: (s: Set<number>) => void, id: number) => {
    const next = new Set(set);
    next.has(id) ? next.delete(id) : next.add(id);
    apply(next);
  };

  // Сколько машин реально попадёт под запуск: явные компы плюс хосты выбранных
  // кабинетов, без повторов (один комп может быть в нескольких кабинетах).
  const distinctTargetCount = (() => {
    const ids = new Set<number>(runHosts);
    for (const gid of runGroups) {
      const group = groups.find((g) => g.id === gid);
      for (const h of group?.hosts || []) ids.add(h.id);
    }
    return ids.size;
  })();

  const targetsSummary = (() => {
    if (runGroups.size === 0 && runHosts.size === 0) return "";
    const parts: string[] = [];
    if (runGroups.size) parts.push(`кабинетов: ${runGroups.size}`);
    if (runHosts.size) parts.push(`компьютеров: ${runHosts.size}`);
    return `${parts.join(", ")} — машин: ${distinctTargetCount}`;
  })();

  const handleRun = async (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedIds.size === 0) { showToast("Выберите хотя бы один сценарий", "error"); return; }
    if (distinctTargetCount === 0) { showToast("Выберите хотя бы одну цель", "error"); return; }
    setActiveRuns([]);
    try {
      const result = await apiPostClient("/api/scenarios/run", {
        scenario_ids: [...selectedIds],
        host_ids: [...runHosts],
        group_ids: [...runGroups],
      });
      showToast(`Сценарии запущены на ${distinctTargetCount} машинах`);
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
            {/* Цели набираются списком: можно взять несколько кабинетов целиком
                и/или отдельные компьютеры — в том числе из другого кабинета. */}
            <div className="label">
              Цели
              <button
                type="button"
                className="input flex items-center justify-between gap-2 text-left"
                onClick={() => setTargetsOpen((v) => !v)}
              >
                <span className={targetsSummary ? "" : "text-gray-400"}>
                  {targetsSummary || "Выберите кабинеты и компьютеры"}
                </span>
                <ChevronDown
                  size={16}
                  className={`shrink-0 transition-transform ${targetsOpen ? "rotate-180" : ""}`}
                />
              </button>
            </div>

            {targetsOpen && (
              <div className="grid md:grid-cols-2 gap-4 rounded-[10px] border border-gray-200 dark:border-gray-700 p-3 max-h-64 overflow-auto">
                <div>
                  <div className="text-sm font-semibold mb-2">Кабинеты</div>
                  {groups.length === 0 && <div className="text-sm text-gray-400">Кабинетов нет</div>}
                  {groups.map((g) => (
                    <label key={g.id} className="flex items-center gap-2 text-sm py-1 cursor-pointer">
                      <input
                        type="checkbox"
                        className="accent-blue-600"
                        checked={runGroups.has(g.id)}
                        onChange={() => toggleIn(runGroups, setRunGroups, g.id)}
                      />
                      <span className="truncate">{g.name}</span>
                      <span className="text-xs text-gray-400 shrink-0">({g.hosts?.length ?? 0})</span>
                    </label>
                  ))}
                </div>
                <div>
                  <div className="text-sm font-semibold mb-2">Компьютеры</div>
                  {hosts.length === 0 && <div className="text-sm text-gray-400">Компьютеров нет</div>}
                  {hosts.map((h) => (
                    <label key={h.id} className="flex items-center gap-2 text-sm py-1 cursor-pointer">
                      <input
                        type="checkbox"
                        className="accent-blue-600"
                        checked={runHosts.has(h.id)}
                        onChange={() => toggleIn(runHosts, setRunHosts, h.id)}
                      />
                      <span className="truncate">{h.name}</span>
                      <span className="text-xs text-gray-400 font-mono shrink-0">{h.address}</span>
                    </label>
                  ))}
                </div>
              </div>
            )}

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
