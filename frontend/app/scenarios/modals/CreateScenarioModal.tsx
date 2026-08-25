"use client";

import { useState } from "react";
import { Modal } from "@/components/Modal";
import { useToast } from "@/components/Toast";
import { apiPostClient } from "@/lib/api-client";
import { Plus, Trash2 } from "lucide-react";
import { Module, Placeholder, StepForm } from "@/lib/scenario-types";

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

interface Props {
  modules: Module[];
  onClose: () => void;
  /** Вызывается после успешного создания — родитель перезагружает данные. */
  onCreated: () => void;
}

/** Модалка создания сценария: название, описание и шаги (модуль + on_failure + аргументы). */
export function CreateScenarioModal({ modules, onClose, onCreated }: Props) {
  const showToast = useToast();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [steps, setSteps] = useState<StepForm[]>([
    { module_id: "", module_slug: "", args: {}, on_failure: "stop" },
  ]);

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
      onCreated();
      onClose();
    } catch (err: any) {
      showToast(err.message, "error");
    }
  };

  return (
    <Modal title="Создать сценарий" onClose={onClose} size="lg">
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
          <h4 className="font-medium text-gray-700 dark:text-gray-300">Шаги сценария</h4>
          {steps.map((step, i) => {
            const mod = modules.find((m) => m.id === parseInt(step.module_id));
            const placeholders = parsePlaceholders(mod?.schema_json);

            return (
              <div key={i} className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 space-y-3">
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
    </Modal>
  );
}
