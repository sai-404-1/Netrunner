"use client";

import { useCallback, useEffect, useState } from "react";
import { apiGetClient, apiPostClient } from "@/lib/api-client";
import { DataTable } from "@/components/DataTable";
import { StatusBadge } from "@/components/Badge";
import { useToast } from "@/components/Toast";
import { Plus, Play, Trash2, ChevronDown, ChevronRight } from "lucide-react";

interface Scenario {
  id: number;
  name: string;
  description: string | null;
  steps: ScenarioStep[];
  step_count: number;
  run_count: number;
}

interface ScenarioStep {
  id: number;
  module_id: number;
  step_order: number;
  step_name: string;
  config_json: string;
  on_failure: string;
}

interface ScenarioRun {
  id: number;
  scenario_id: number;
  scenario_name: string;
  target_type: string;
  target_id: number;
  status: string;
  started_at: string;
  finished_at: string | null;
  step_runs: ScenarioStepRun[];
}

interface ScenarioStepRun {
  id: number;
  step_id: number;
  host_id: number;
  module_id: number;
  status: string;
  output_text: string | null;
  error_text: string | null;
  exit_code: number | null;
}

interface Module {
  id: number;
  name: string;
  slug: string;
  supports_task_runner: boolean;
  schema_json?: string;
}

interface SelectOption {
  value: string;
  label: string;
}

interface Placeholder {
  name: string;
  label: string;
  default: string;
  type: string;
  options: SelectOption[];
}

interface StepForm {
  module_id: string;
  module_slug: string;
  args: Record<string, string>;
  on_failure: string;
}

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

  const handleRun = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!runScenarioId || !runTargetId) { showToast("Выберите сценарий и цель", "error"); return; }

    setRunResult("Запуск...");
    try {
      const result = await apiPostClient("/api/scenarios/run", {
        scenario_id: parseInt(runScenarioId),
        target_type: runTargetType,
        target_id: parseInt(runTargetId),
      });
      let text = `Статус: ${result.status}\n\n`;
      if (result.step_runs) {
        for (const sr of result.step_runs) {
          const icon = sr.status === "completed" ? "✓" : sr.status === "failed" ? "✗" : "○";
          text += `${icon} [${sr.status}] host#${sr.host_id} step#${sr.step_id}\n`;
          if (sr.output_text) text += `  ${sr.output_text.substring(0, 300)}\n`;
          if (sr.error_text) text += `  ERROR: ${sr.error_text.substring(0, 200)}\n`;
        }
      }
      setRunResult(text);
      showToast("Сценарий выполнен: " + result.status);
      loadData();
      loadRuns();
    } catch (err: any) {
      setRunResult("Ошибка: " + err.message);
      showToast(err.message, "error");
    }
  };

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
        <h3 className="font-semibold mb-4">Создать сценарий</h3>
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
      </div>

      {/* Scenario list */}
      <div className="panel">
        <h3 className="font-semibold mb-4">Существующие сценарии</h3>
        {loading ? (
          <p className="text-gray-500">Загрузка...</p>
        ) : scenarios.length === 0 ? (
          <p className="text-gray-400">Сценариев пока нет</p>
        ) : (
          <div className="space-y-2">
            {scenarios.map((sc) => (
              <div key={sc.id} className="border border-gray-200 rounded-lg overflow-hidden">
                <button
                  className="w-full flex items-center justify-between p-3 hover:bg-gray-50 text-left"
                  onClick={() =>
                    setExpandedScenarios((prev) => {
                      const next = new Set(prev);
                      next.has(sc.id) ? next.delete(sc.id) : next.add(sc.id);
                      return next;
                    })
                  }
                >
                  <div className="flex items-center gap-3">
                    {expandedScenarios.has(sc.id) ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                    <span className="font-medium">{sc.name}</span>
                    <span className="text-sm text-gray-500">{sc.description}</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-gray-500">
                    <span>{sc.step_count} шагов</span>
                    <button className="btn-danger py-1 px-2" onClick={(e) => { e.stopPropagation(); handleDelete(sc.id); }}>
                      <Trash2 size={14} />
                    </button>
                  </div>
                </button>
                {expandedScenarios.has(sc.id) && (
                  <div className="border-t border-gray-200 p-3 bg-gray-50">
                    {sc.steps && sc.steps.length > 0 ? (
                      <ul className="space-y-1 text-sm">
                        {sc.steps.map((step, i) => (
                          <li key={step.id} className="flex gap-2">
                            <span className="text-gray-400">{i + 1}.</span>
                            <span className="font-medium">{step.step_name}</span>
                            <span className="text-gray-500">
                              (модуль #{step.module_id}, on_failure: {step.on_failure}, config: {step.config_json})
                            </span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-gray-400 text-sm">Нет шагов</p>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

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

      {/* Run result */}
      <div className="panel">
        <h3 className="font-semibold mb-4">История запусков</h3>
        {runs.length === 0 ? (
          <p className="text-gray-400">Запусков пока нет</p>
        ) : (
          <div className="space-y-2">
            {runs.map((run) => (
              <div key={run.id} className="flex items-center justify-between p-2 border border-gray-200 rounded-lg text-sm">
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
      </div>
    </div>
  );
}
