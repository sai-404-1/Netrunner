"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiGetClient, apiPostClient } from "@/lib/api-client";
import { StatusBadge } from "@/components/Badge";
import { useToast } from "@/components/Toast";
import { Plus, Play, Trash2, Loader2, CheckCircle2, XCircle, Circle, ChevronLeft } from "lucide-react";
import { Scenario, Placeholder, Module, ScenarioRun, StepForm } from "@/lib/scenario-types";
import ScenariosList from "./ScenariosList";

function parsePlaceholders(schema_json?: string): Placeholder[] {
  if (!schema_json) return [];
  try {
    const schema = JSON.parse(schema_json);
    return (schema.placeholders || []).map(([name, label, def, type, options]: any) => ({
      name,
      label,
      default: String(def ?? ""),
      type: type || "text",
      options: (options || []).map((o: any) =>
        Array.isArray(o) ? { value: String(o[0]), label: String(o[1]) } : { value: String(o), label: String(o) }
      ),
    }));
  } catch {
    return [];
  }
}

export default function ScenariosPage() {
  const showToast = useToast();
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [modules, setModules] = useState<Module[]>([]);
  const [runs, setRuns] = useState<ScenarioRun[]>([]);
  const [expandedScenarios, setExpandedScenarios] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(true);

  // Form state
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [steps, setSteps] = useState<StepForm[]>([
    { module_id: "", module_slug: "", args: {}, on_failure: "stop" },
  ]);

  // Run form state
  const [runScenarioId, setRunScenarioId] = useState("");
  const [runTargetType, setRunTargetType] = useState("host");
  const [runTargetId, setRunTargetId] = useState("");
  const [hosts, setHosts] = useState<{ id: number; name: string }[]>([]);
  const [groups, setGroups] = useState<{ id: number; name: string }[]>([]);
  const [runResult, setRunResult] = useState<string>("");
  const [addSceranioCollapsed, setSceranioCollapsed] = useState(true);
  const [activeRun, setActiveRun] = useState<ScenarioRun | null>(null);
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

  // Reset args when module changes for a step
  const resetArgsForModule = (moduleId: string, stepIndex: number) => {
    const mod = modules.find((m) => m.id === parseInt(moduleId));
    if (!mod) return;

    const placeholders = parsePlaceholders(mod.schema_json);
    const defaults: Record<string, string> = {};
    for (const p of placeholders) defaults[p.name] = p.default;

    setSteps((prev) => {
      const next = [...prev];
      next[stepIndex] = { ...next[stepIndex], module_id: moduleId, module_slug: mod.slug, args: defaults };
      return next;
    });
  };

  const addStep = () => {
    setSteps([...steps, { module_id: "", module_slug: "", args: {}, on_failure: "stop" }]);
  };

  const updateStep = (index: number, field: string, value: string) => {
    if (field === "module_id") {
      resetArgsForModule(value, index);
    } else {
      setSteps((prev) => {
        const next = [...prev];
        (next[index] as any)[field] = value;
        return next;
      });
    }
  };

  const updateStepArg = (index: number, argName: string, value: string) => {
    setSteps((prev) => {
      const next = [...prev];
      next[index].args = { ...next[index].args, [argName]: value };
      return next;
    });
  };

  const removeStep = (index: number) => {
    if (steps.length > 1) {
      setSteps(steps.filter((_, i) => i !== index));
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) { showToast("Введите название сценария", "error"); return; }

    const validSteps = steps
      .filter((s) => s.module_id)
      .map((s) => {
        const mod = modules.find((m) => m.id === parseInt(s.module_id));
        return {
          module_id: parseInt(s.module_id),
          step_name: mod?.name || `Шаг`,
          config: s.args,
          on_failure: s.on_failure,
        };
      });

    if (!validSteps.length) { showToast("Добавьте хотя бы один шаг", "error"); return; }

    try {
      await apiPostClient("/api/scenarios", { name: name.trim(), description: description.trim(), steps: validSteps });
      showToast("Сценарий создан");
      setName("");
      setDescription("");
      setSteps([{ module_id: "", module_slug: "", args: {}, on_failure: "stop" }]);
      loadData();
    } catch (err: any) {
      showToast(err.message, "error");
    }
  };

  const pollRun = useCallback((runId: number) => {
    apiGetClient(`/api/scenarios/runs/${runId}`)
      .then((data: ScenarioRun) => {
        setActiveRun(data);
        if (data.status === "running" || data.status === "pending") {
          pollRef.current = setTimeout(() => pollRun(runId), 1000);
        } else {
          loadRuns();
          loadData();
        }
      })
      .catch(() => {});
  }, [loadRuns, loadData]);

  const handleRun = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!runScenarioId || !runTargetId) { showToast("Выберите сценарий и цель", "error"); return; }
    setRunResult("");
    setActiveRun(null);
    if (pollRef.current) clearTimeout(pollRef.current);
    try {
      const result = await apiPostClient("/api/scenarios/run", {
        scenario_id: parseInt(runScenarioId),
        target_type: runTargetType,
        target_id: parseInt(runTargetId),
      });
      showToast("Сценарий запущен");
      pollRun(result.run_id);
    } catch (err: any) {
      showToast(err.message, "error");
    }
  };

  useEffect(() => {
    return () => {
      if (pollRef.current) clearTimeout(pollRef.current);
    };
  }, []);

  const handleDelete = async (id: number) => {
    try {
      await apiPostClient("/api/scenarios/delete", { id });
      showToast("Сценарий удалён");
      loadData();
    } catch (err: any) {
      showToast(err.message, "error");
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold">Сценарии</h2>
        <p className="text-gray-500">Многошаговые сценарии для автоматизации действий на хостах</p>
      </div>

      {/* Create form */}
      <div className="panel">
        <div className={"flex items-center justify-between " + (addSceranioCollapsed ? "mb-0" : "mb-4")}>
          <h3 className="font-semibold">Создать сценарий</h3>
          <button
              type="button"
              className="btn-secondary p-1.5"
              onClick={() => setSceranioCollapsed((v) => !v)}
              title={addSceranioCollapsed ? "Развернуть" : "Свернуть"}
            >
              <ChevronLeft size={16} className={`transition-transform duration-200 ${addSceranioCollapsed ? "" : "rotate-180"}`} />
          </button>
        </div>
        { !addSceranioCollapsed && (
        
        <form onSubmit={handleCreate} className="space-y-4">
          <div className="grid md:grid-cols-2 gap-4">
            <label className="label">
              Название
              <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Мой сценарий" />
            </label>
            <label className="label">
              Описание
              <input className="input" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Описание сценария" />
            </label>
          </div>

          <div className="space-y-3">
            <h4 className="font-medium text-gray-700">Шаги сценария</h4>
            {steps.map((step, i) => {
              const mod = modules.find((m) => m.id === parseInt(step.module_id));
              const placeholders = parsePlaceholders(mod?.schema_json);

              return (
                <div key={i} className="border border-gray-200 rounded-lg p-4 space-y-3">
                  <div className="flex items-start justify-between gap-3 flex-wrap">
                    <div className="grid sm:grid-cols-3 gap-3 flex-1">
                      <label className="label mb-0">
                        Модуль
                        <select className="input" value={step.module_id} onChange={(e) => updateStep(i, "module_id", e.target.value)}>
                          <option value="">Выберите модуль</option>
                          {modules.map((m) => (
                            <option key={m.id} value={m.id}>{m.name} ({m.slug})</option>
                          ))}
                        </select>
                      </label>
                      <label className="label mb-0">
                        On failure
                        <select className="input" value={step.on_failure} onChange={(e) => updateStep(i, "on_failure", e.target.value)}>
                          <option value="stop">STOP</option>
                          <option value="skip">SKIP</option>
                        </select>
                      </label>
                      <div className="flex items-end justify-end">
                        <button type="button" className="btn-danger py-1.5 px-3" onClick={() => removeStep(i)} disabled={steps.length <= 1}>
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Dynamic fields from module schema */}
                  {step.module_id && placeholders.length > 0 && (
                    <div className="grid md:grid-cols-2 gap-3 pt-2 border-t border-gray-100">
                      {placeholders.map((p) => (
                        <label key={p.name} className={`label mb-0${p.type === "textarea" ? " md:col-span-2" : ""}`}>
                          {p.label}
                          {p.type === "textarea" ? (
                            <textarea
                              className="input font-mono"
                              rows={2}
                              value={step.args[p.name] ?? p.default}
                              onChange={(e) => updateStepArg(i, p.name, e.target.value)}
                              placeholder={p.default}
                            />
                          ) : p.type === "radio" ? (
                            <div className="flex gap-4 flex-wrap mt-1">
                              {p.options.map((o) => (
                                <label key={o.value} className="flex items-center gap-1.5 cursor-pointer text-sm">
                                  <input
                                    type="radio"
                                    name={`step-${i}-${p.name}`}
                                    value={o.value}
                                    checked={(step.args[p.name] ?? p.default) === o.value}
                                    onChange={() => updateStepArg(i, p.name, o.value)}
                                    className="accent-blue-600"
                                  />
                                  {o.label}
                                </label>
                              ))}
                            </div>
                          ) : p.type === "select" ? (
                            <select
                              className="input"
                              value={step.args[p.name] ?? p.default}
                              onChange={(e) => updateStepArg(i, p.name, e.target.value)}
                            >
                              {p.options.map((o) => (
                                <option key={o.value} value={o.value}>{o.label}</option>
                              ))}
                            </select>
                          ) : (
                            <input
                              className="input"
                              type={p.type === "password" ? "password" : "text"}
                              value={step.args[p.name] ?? p.default}
                              onChange={(e) => updateStepArg(i, p.name, e.target.value)}
                              placeholder={p.default}
                            />
                          )}
                        </label>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
          <div className="flex gap-3">
            <button type="button" className="btn-secondary" onClick={addStep}>
              <Plus size={16} /> Добавить шаг
            </button>
            <button className="btn" type="submit">Создать сценарий</button>
          </div>
        </form>
        ) }
      </div>

      {/* Scenario list */}
      <ScenariosList
        scenarios={scenarios}
        loading={loading}
        expandedScenarios={expandedScenarios}
        setExpandedScenarios={setExpandedScenarios}
        handleDelete={handleDelete}
      />

      {/* Run form */}
      <div className="panel">
        <h3 className="font-semibold mb-4">Запустить сценарий</h3>
        <form onSubmit={handleRun} className="space-y-3">
          <div className="grid md:grid-cols-3 gap-4 items-end">
            <label className="label">
              Сценарий
              <select className="input" value={runScenarioId} onChange={(e) => setRunScenarioId(e.target.value)}>
                <option value="">Выберите сценарий</option>
                {scenarios.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            </label>
            <label className="label">
              Тип цели
              <select className="input" value={runTargetType} onChange={(e) => setRunTargetType(e.target.value)}>
                <option value="host">Хост</option>
                <option value="group">Группа</option>
              </select>
            </label>
            <label className="label">
              ID цели
              <select className="input" value={runTargetId} onChange={(e) => setRunTargetId(e.target.value)}>
                {(runTargetType === "host" ? hosts : groups).map((t) => (
                  <option key={t.id} value={t.id}>{t.name} #{t.id}</option>
                ))}
              </select>
            </label>
          </div>
          <button className="btn" type="submit">
            <Play size={16} /> Запустить
          </button>
        </form>
      </div>

      {/* Живое выполнение: какой шаг/модуль активен */}
      {activeRun &&
        (() => {
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
            <div className="panel">
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
                        st.state === "running" ? "border-blue-400 bg-blue-50" : "dark:border-gray-700"
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
        })()}

      {/* Run result */}
      {/* <div className="panel">
        <h3 className="font-semibold mb-4">История запусков</h3>
        {runs.length === 0 ? (
          <p className="text-gray-400">Запусков пока нет</p>
        ) : (
          <div className="space-y-2">
            {runs.map((run) => (
              <div key={run.id} className="flex items-center justify-between p-2 border dark:border-gray-700 rounded-lg text-sm">
                <span className="font-medium">{run.scenario_name}</span>
                <StatusBadge status={run.status} />
                <span className="text-gray-500">{new Date(run.started_at).toLocaleString()}</span>
              </div>
            ))}
          </div>
        )}
        {runResult && (
          <pre className="mt-4 bg-slate-950 text-gray-200 rounded-[10px] p-4 text-sm min-h-[100px] overflow-auto">
            {runResult}
          </pre>
        )}
      </div> */}
    </div>
  );
}
