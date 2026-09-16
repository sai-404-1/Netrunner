import { useState } from "react";
import { ChevronDown, ChevronRight, Folder, Pencil, Trash2 } from "lucide-react";
import { Scenario, ScenarioFolder } from "@/lib/scenario-types";

interface Props {
    scenarios: Scenario[];
    folders: ScenarioFolder[];
    loading: boolean;
    /** Выбранные (мульти-выбор) id сценариев для запуска. */
    selectedIds: Set<number>;
    /** Клик по названию карточки — выбрать/снять (мульти-выбор). */
    onToggle: (id: number) => void;
    /** Кнопка-карандаш — открыть редактирование. */
    onEdit: (scenario: Scenario) => void;
    /** Папками управляет только администратор; преподаватель их просто видит. */
    canManageFolders: boolean;
    onRenameFolder: (folder: ScenarioFolder) => void;
    onDeleteFolder: (folder: ScenarioFolder) => void;
}

export default function Scenarios({
    scenarios,
    folders,
    loading,
    selectedIds,
    onToggle,
    onEdit,
    canManageFolders,
    onRenameFolder,
    onDeleteFolder,
}: Props) {
    // Свёрнутые папки: по умолчанию все развёрнуты, состояние живёт только в сессии.
    const [collapsed, setCollapsed] = useState<Set<number>>(new Set());

    const toggleFolder = (id: number) => {
        setCollapsed((prev) => {
            const next = new Set(prev);
            next.has(id) ? next.delete(id) : next.add(id);
            return next;
        });
    };

    const rootScenarios = scenarios.filter((sc) => !sc.folder_id);

    const renderCards = (items: Scenario[]) => (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {items.map((sc) => {
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
    );

    return (
        <div className="panel">
            <h3 className="font-semibold mb-4">Существующие сценарии</h3>
            {loading ? (
                <p className="text-gray-500">Загрузка...</p>
            ) : scenarios.length === 0 ? (
                <p className="text-gray-400">Сценариев пока нет</p>
            ) : (
                <div className="space-y-4">
                    {folders.map((folder) => {
                        const items = scenarios.filter((sc) => sc.folder_id === folder.id);
                        const isCollapsed = collapsed.has(folder.id);
                        return (
                            <div key={folder.id} className="rounded-2xl border border-gray-200 dark:border-gray-700">
                                <div className="flex items-center gap-2 px-3 py-2">
                                    <button
                                        type="button"
                                        className="flex items-center gap-2 flex-1 text-left font-medium"
                                        onClick={() => toggleFolder(folder.id)}
                                        title={isCollapsed ? "Развернуть" : "Свернуть"}
                                    >
                                        {isCollapsed ? <ChevronRight size={16} /> : <ChevronDown size={16} />}
                                        <Folder size={16} className="text-blue-600 dark:text-blue-400" />
                                        <span className="truncate">{folder.name}</span>
                                        <span className="text-xs text-gray-500">{items.length}</span>
                                    </button>
                                    {canManageFolders && (
                                        <>
                                            <button
                                                type="button"
                                                className="btn-secondary p-1.5 shrink-0"
                                                onClick={() => onRenameFolder(folder)}
                                                title="Переименовать папку"
                                            >
                                                <Pencil size={14} />
                                            </button>
                                            <button
                                                type="button"
                                                className="btn-secondary p-1.5 shrink-0"
                                                onClick={() => onDeleteFolder(folder)}
                                                title="Удалить папку (сценарии останутся)"
                                            >
                                                <Trash2 size={14} />
                                            </button>
                                        </>
                                    )}
                                </div>
                                {!isCollapsed && (
                                    <div className="px-3 pb-3">
                                        {items.length === 0 ? (
                                            <p className="text-sm text-gray-400">Папка пуста</p>
                                        ) : (
                                            renderCards(items)
                                        )}
                                    </div>
                                )}
                            </div>
                        );
                    })}

                    {rootScenarios.length > 0 && (
                        <div>
                            {folders.length > 0 && (
                                <p className="text-xs text-gray-500 mb-2">Вне папок</p>
                            )}
                            {renderCards(rootScenarios)}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
