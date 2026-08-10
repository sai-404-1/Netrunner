import { Scenario, Placeholder, Module, ScenarioRun, StepForm } from "@/lib/scenario-types";
import { ChevronDown, ChevronRight, Trash2 } from "lucide-react";
import { Dispatch, SetStateAction } from "react"; // 1. Импортируем типы React

interface Props {
    scenarios: Scenario[];
    loading: boolean;
    expandedScenarios: Set<number>;
    handleDelete: (id: number) => void;
    prev?: StepForm[]; 
    setExpandedScenarios: Dispatch<SetStateAction<Set<number>>>;
}

export default function Scenarios({ scenarios, loading, expandedScenarios, setExpandedScenarios, handleDelete, prev }: Props) {
    return (
        <div className="panel">
        <h3 className="font-semibold mb-4">Существующие сценарии</h3>
        {loading ? (
          <p className="text-gray-500">Загрузка...</p>
        ) : scenarios.length === 0 ? (
          <p className="text-gray-400">Сценариев пока нет</p>
        ) : (
          <div className="space-y-2">
            {scenarios.map((sc) => (
              <div key={sc.id} className="overflow-auto border border-gray-200 dark:border-gray-700 rounded-2xl bg-white dark:bg-gray-800">
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
                  <div className="border-t dark:border-gray-700 p-3 bg-gray-50">
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
    )
}