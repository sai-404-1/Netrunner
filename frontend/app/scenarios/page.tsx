"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiGetClient, apiPostClient } from "@/lib/api-client";
import { StatusBadge } from "@/components/Badge";
import { useToast } from "@/components/Toast";
import { Play, Loader2, CheckCircle2, XCircle, Circle, Plus, X } from "lucide-react";
import { Scenario, Module, ScenarioRun } from "@/lib/scenario-types";
import ScenariosList from "./ScenariosList";
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
  const [activeRuns, setActiveRuns] = useState<ScenarioRun[]>([]);
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);

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
    try {
      const runsData = await apiGetClient("/api/scenarios/runs?limit=20");
      setRuns(runsData);
    } catch {
      // silent
    }
  }, []);

  useEffect(() => {
    loadData();
    loadRuns();
  }, [loadData, loadRuns]);

  // Опрос нескольких активных запусков (по очереди запущенных сценариев)
  const pollRuns = useCallback((runIds: number[]) => {
    Promise.all(runIds.map((id) => apiGetClient(`/api/scenarios/runs/${id}`)))
      .then((data: ScenarioRun[]) => {
        setActiveRuns(data);
        const anyActive = data.some((r) => r.status === "running" || r.status === "pending");
        if (anyActive) {
          pollRef.current = setTimeout(() => pollRuns(runIds), 1500);
        } else {
          loadRuns();
          loadData();
        }
      })
      .catch(() => {});
  }, [loadRuns, loadData]);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearTimeout(pollRef.current);
    };
  }, []);

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
    if (pollRef.current) clearTimeout(pollRef.current);
    try {
      const result = await apiPostClient("/api/scenarios/run", {
        scenario_ids: [...selectedIds],
        target_type: runTargetType,
        target_id: parseInt(runTargetId),
      });
      showToast("Сценарии запущены");
      pollRuns(result.run_ids || [result.run_id]);
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

  const selectedScenarios = scenarios.filter((s) => selectedIds.has(s.id));

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold">Сценарии</h2>
        <p className="text-gray-500">Многошаговые сценарии для автоматизации действий на хостах</p>
      </div>

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

      {/* Живое выполнение: активные запуски и их шаги/модули */}
      {activeRuns.length > 0 && (
        <div className="space-y-4">
          {activeRuns.map((activeRun) => {
            const sc = scenarios.find((s) => s.id === activeRun.scenario_id);
            const orderedSteps = (sc?.steps || []).slice().sort((a, b) => a.step_order - b.step_order);
            const stepStat = (stepId: number) => {
              const srs = activeRun.step_runs.filter((r) => r.step_id === stepId);
              const running = srs.some((r) => r.status === "running" || r.status === "pending");
              const failed = srs.filter((r) => r.status === "failed").length;
              const done = srs.filter((r) => r.status === "completed").length;
              const state = srs.length === 0 ? "queued" : running ? "running" : failed > 0 ? "failed" : "done";
              return { state, done, failed, total: srs.length };
            };
            return (
              <div key={activeRun.id} className="panel">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-semibold">Выполнение: {activeRun.scenario_name}</h3>
                  <StatusBadge status={activeRun.status} />
                </div>
                <div className="space-y-2">
                  {orderedSteps.map((step) => {
                    const st = stepStat(step.id);
                    const moduleName = modules.find((m) => m.id === step.module_id)?.name || "";
                    return (
                      <div
                        key={step.id}
                        className={`flex items-center justify-between gap-3 p-3 rounded-lg border ${
                          st.state === "running" ? "border-blue-400 bg-blue-50 dark:bg-blue-950/40" : "dark:border-gray-700"
                        }`}
                      >
                        <span className="flex items-center gap-2 min-w-0">
                          {st.state === "running" ? (
                            <Loader2 size={16} className="animate-spin text-blue-500 shrink-0" />
                          ) : st.state === "done" ? (
                            <CheckCircle2 size={16} className="text-green-500 shrink-0" />
                          ) : st.state === "failed" ? (
                            <XCircle size={16} className="text-red-500 shrink-0" />
                          ) : (
                            <Circle size={16} className="text-gray-400 shrink-0" />
                          )}
                          <strong className="truncate">
                            {step.step_order}. {step.step_name || moduleName}
                          </strong>
                          {moduleName && <span className="text-gray-500 text-xs shrink-0">{moduleName}</span>}
                        </span>
                        <span className="text-xs text-gray-500 shrink-0">
                          {st.total > 0
                            ? `${st.done}/${st.total} готово${st.failed ? `, ${st.failed} ошибок` : ""}`
                            : "в очереди"}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Scenario list — карточки: клик выбирает (мульти-выбор), карандаш редактирует */}
      <ScenariosList
        scenarios={scenarios}
        loading={loading}
        selectedIds={selectedIds}
        onToggle={toggleSelect}
        onEdit={setEditScenario}
      />

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
