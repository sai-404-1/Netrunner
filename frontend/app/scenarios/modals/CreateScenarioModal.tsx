"use client";

import { useEffect, useState } from "react";
import { Modal } from "@/components/Modal";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { useToast } from "@/components/Toast";
import { apiPostClient } from "@/lib/api-client";
import { Plus, Trash2 } from "lucide-react";
import { Module, Placeholder, StepForm, Scenario } from "@/lib/scenario-types";
import { FileManager } from "@/components/FileManager";

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

/** Превращает шаг сценария (config_json) в форму редактирования. */
function stepToForm(step: { id: number; module_id: number; step_name: string; config_json: string; on_failure: string }): StepForm {
  let args: Record<string, string> = {};
  let fileIds: number[] | undefined;
  try {
    const parsed = JSON.parse(step.config_json || "{}");
    if (parsed && typeof parsed === "object") {
      // file_ids — массив, держим отдельно (в args он превратится в строку)
      if (Array.isArray(parsed.file_ids)) {
        fileIds = parsed.file_ids.map((x: unknown) => Number(x)).filter((n: number) => Number.isFinite(n));
      }
      args = Object.fromEntries(
        Object.entries(parsed)
          .filter(([k]) => k !== "file_ids")
          .map(([k, v]) => [k, String(v ?? "")])
      );
    }
  } catch {
    args = {};
  }
  return { module_id: String(step.module_id), module_slug: "", args, file_ids: fileIds, on_failure: step.on_failure || "stop" };
}

interface Props {
  modules: Module[];
  onClose: () => void;
  /** Вызывается после успешного сохранения — родитель перезагружает данные. */
  onSaved: () => void;
  /** Передан — режим редактирования; иначе создание. */
  scenario?: Scenario | null;
  /** Удаление сценария (только в режиме редактирования). */
  onDelete?: () => void;
}

/** Модалка создания/редактирования сценария: название, разворачиваемое описание и шаги (модуль + on_failure + аргументы). */
export function CreateScenarioModal({ modules, onClose, onSaved, scenario, onDelete }: Props) {
  const editing = Boolean(scenario);
  const showToast = useToast();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [descExpanded, setDescExpanded] = useState(false);
  const [steps, setSteps] = useState<StepForm[]>([
    { module_id: "", module_slug: "", args: {}, on_failure: "stop" },
  ]);
  const [saving, setSaving] = useState(false);
  // подтверждения удаления
  const [confirmStep, setConfirmStep] = useState<number | null>(null);
  const [confirmScenario, setConfirmScenario] = useState(false);

  // При открытии в режиме редактирования — заполнить состояние из сценария.
  useEffect(() => {
    if (scenario) {
      setName(scenario.name);
      setDescription(scenario.description || "");
      if (scenario.steps && scenario.steps.length > 0) {
        setSteps(scenario.steps.map(stepToForm));
      }
    }
  }, [scenario]);

  const resetArgsForModule = (moduleId: string, stepIndex: number) => {
    const mod = modules.find((m) => m.id === parseInt(moduleId));
    if (!mod) return;

    const placeholders = parsePlaceholders(mod.schema_json);
    const defaults: Record<string, string> = {};
    for (const p of placeholders) defaults[p.name] = p.default;

    setSteps((prev) => {
      const next = [...prev];
      next[stepIndex] = { ...next[stepIndex], module_id: moduleId, module_slug: mod.slug, args: defaults, file_ids: undefined };
      return next;
    });
  };

  const updateStepFileIds = (index: number, ids: number[]) => {
    setSteps((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], file_ids: ids };
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

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) { showToast("Введите название сценария", "error"); return; }

    const validSteps = steps
      .filter((s) => s.module_id)
      .map((s) => {
        const mod = modules.find((m) => m.id === parseInt(s.module_id));
        const config: Record<string, unknown> = { ...s.args };
        // file_distribute: file_ids сохраняем МАССИВОМ (иначе модуль не получит файлы)
        if (s.file_ids && s.file_ids.length > 0) config.file_ids = s.file_ids;
        return {
          module_id: parseInt(s.module_id),
          step_name: mod?.name || `Шаг`,
          config,
          on_failure: s.on_failure,
        };
      });

    if (!validSteps.length) { showToast("Добавьте хотя бы один шаг", "error"); return; }

    setSaving(true);
    try {
      if (editing && scenario) {
        await apiPostClient("/api/scenarios/update", {
          scenario_id: scenario.id,
          name: name.trim(),
          description: description.trim(),
          steps: validSteps,
        });
        showToast("Сценарий обновлён");
      } else {
        await apiPostClient("/api/scenarios", { name: name.trim(), description: description.trim(), steps: validSteps });
        showToast("Сценарий создан");
      }
      onSaved();
      onClose();
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal title={editing ? "Редактировать сценарий" : "Создать сценарий"} onClose={onClose} size="lg">
      <form onSubmit={handleSave} className="space-y-4">
        <div className="space-y-4">
          <label className="label">
            Название
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Мой сценарий" />
          </label>

          {/* Описание — сворачиваемое: в потоке 2 строки, по клику/фокусу разворачивается плавающей панелью ПОВЕРХ нижележащего */}
          <div className="relative">
            <label className="label mb-0">
              Описание
              <textarea
                className="input"
                rows={2}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Описание сценария"
                onFocus={() => setDescExpanded(true)}
              />
            </label>
            {descExpanded && (
              <div className="absolute inset-x-0 top-0 z-30 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 p-2 shadow-2xl">
                <label className="label mb-0">
                  Описание
                  <textarea
                    className="input"
                    rows={8}
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Описание сценария"
                    autoFocus
                  />
                </label>
                <div className="flex justify-end mt-2">
                  <button type="button" className="btn-secondary py-1 px-2 text-xs" onClick={() => setDescExpanded(false)}>
                    Свернуть описание
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="space-y-3">
          <h4 className="font-medium text-gray-700 dark:text-gray-300">Шаги сценария</h4>
          {steps.map((step, i) => {
            const mod = modules.find((m) => m.id === parseInt(step.module_id));
            const placeholders = parsePlaceholders(mod?.schema_json);

            return (
              <div key={i} className="border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/60 rounded-lg p-4 space-y-3">
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
                      <button type="button" className="btn-danger py-1.5 px-3" onClick={() => setConfirmStep(i)} disabled={steps.length <= 1}>
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </div>
                </div>

                {/* Dynamic fields from module schema */}
                {step.module_id && placeholders.length > 0 && (
                  <div className="grid md:grid-cols-2 gap-3 pt-2 border-t border-gray-100 dark:border-gray-700">
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

                {/* file_distribute: выбор файлов из хранилища Netrunner */}
                {step.module_id && mod?.slug === "file_distribute" && (
                  <div className="pt-2 border-t border-gray-100 dark:border-gray-700">
                    <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Файлы для рассылки ({step.file_ids?.length ?? 0} выбрано)
                    </p>
                    <FileManager
                      selectedIds={step.file_ids ?? []}
                      onSelectionChange={(ids) => updateStepFileIds(i, ids)}
                    />
                  </div>
                )}
              </div>
            );
          })}
        </div>
        <div className="flex gap-3">
          {editing && onDelete && (
            <button type="button" className="btn-danger" onClick={() => setConfirmScenario(true)}>
              <Trash2 size={16} /> Удалить сценарий
            </button>
          )}
          <button type="button" className="btn-secondary" onClick={addStep}>
            <Plus size={16} /> Добавить шаг
          </button>
          <button className="btn" type="submit" disabled={saving}>
            {saving ? "Сохранение..." : editing ? "Сохранить" : "Создать сценарий"}
          </button>
        </div>
      </form>

      {confirmScenario && (
        <ConfirmDialog
          title="Удалить сценарий"
          message={`Вы действительно хотите удалить сценарий «${name}»? Это действие необратимо.`}
          onConfirm={() => onDelete?.()}
          onClose={() => setConfirmScenario(false)}
        />
      )}
      {confirmStep !== null && (
        <ConfirmDialog
          title="Удалить шаг"
          message="Вы действительно хотите удалить этот шаг сценария?"
          onConfirm={() => removeStep(confirmStep)}
          onClose={() => setConfirmStep(null)}
        />
      )}
    </Modal>
  );
}
