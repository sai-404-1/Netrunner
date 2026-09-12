import { Pencil } from "lucide-react";
import { Scenario } from "@/lib/scenario-types";
interface Props {
    scenarios: Scenario[];
    loading: boolean;
    /** Выбранные (мульти-выбор) id сценариев для запуска. */
    selectedIds: Set<number>;
    /** Клик по названию карточки — выбрать/снять (мульти-выбор). */
    onToggle: (id: number) => void;
    /** Кнопка-карандаш — открыть редактирование. */
    onEdit: (scenario: Scenario) => void;
}

export default function Scenarios({ scenarios, loading, selectedIds, onToggle, onEdit }: Props) {
    return (
        <div className="panel">
            <h3 className="font-semibold mb-4">Существующие сценарии</h3>
            {loading ? (
                <p className="text-gray-500">Загрузка...</p>
            ) : scenarios.length === 0 ? (
                <p className="text-gray-400">Сценариев пока нет</p>
            ) : (
                /* Сетка карточек: клик по названию = выбрать (мульти-выбор), карандаш справа = редактировать */
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                    {scenarios.map((sc) => {
                        const selected = selectedIds.has(sc.id);
                        return (
                            <div
                                key={sc.id}
                                className={`rounded-2xl border p-1.5 transition-colors ${
                                    selected
                                        ? "border-blue-600 bg-blue-50 dark:bg-blue-950/40"
                                        : "border-gray-200 dark:border-gray-700"
                                }`}
                            >
                                <div className="flex items-center gap-1.5">
                                    <button
                                        type="button"
                                        className={`btn-secondary text-left flex-1 justify-center px-3 py-2 font-medium truncate ${
                                            selected ? "border-blue-600 text-blue-700 dark:text-blue-300" : ""
                                        }`}
                                        onClick={() => onToggle(sc.id)}
                                        title={selected ? "Снять выбор" : "Выбрать для запуска"}
                                    >
                                        {sc.name}
                                    </button>
                                    <button
                                        type="button"
                                        className="btn-secondary p-2 shrink-0"
                                        onClick={() => onEdit(sc)}
                                        title="Редактировать"
                                    >
                                        <Pencil size={16} />
                                    </button>
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    )
}
