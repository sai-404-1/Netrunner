"use client";

import {useCallback, useState} from "react";
import {
  RefreshCw,
  Search,
  CheckSquare,
  PlusIcon,
  List,
  LayoutGrid,
  Pencil,
  Trash2, X,
} from "lucide-react";
import {DataTable} from "@/components/DataTable";
import {HostBoardView} from "@/components/HostBoardView";
import {HostStatusGrid} from "@/components/HostStatusGrid";
import type {Group, Host} from "@/lib/host-types";

interface Props {
  onHosts: (h: Host[]) => void;
  hosts: Host[];
  filteredHosts: Host[];
  groups: Group[];
  search: string;
  groupFilter: string;
  selectedGroupName: string | null;
  checkingAll: boolean;
  selectionMode: boolean;
  selectedIds: Set<number>;
  onSearch: (s: string) => void;
  onGroupFilter: (s: string) => void;
  onSelectGroup: (id: string) => void;
  onClearGroupFilter: () => void;
  onCheckAll: () => void;
  onToggleSelectionMode: () => void;
  onToggleSelect: (id: number) => void;
  onAddHost: () => void;
  onInfoHost: (h: Host) => void;
  onEditGroup: (g: Group) => void;
  onDeleteGroup: (id: number) => void;
  onBoardsChange: () => void;
}

/** Основной рендер страницы «Хосты»: заголовок, переключатель вида, сетка/доска, таблица групп.
 *  Stateless — все данные и колбэки приходят от родителя. */
export function HostList({
                           onHosts,
                           hosts,
                           filteredHosts,
                           groups,
                           search,
                           groupFilter,
                           selectedGroupName,
                           checkingAll,
                           selectionMode,
                           selectedIds,
                           onSearch,
                           onGroupFilter,
                           onSelectGroup,
                           onClearGroupFilter,
                           onCheckAll,
                           onToggleSelectionMode,
                           onToggleSelect,
                           onAddHost,
                           onInfoHost,
                           onEditGroup,
                           onDeleteGroup,
                           onBoardsChange,
                         }: Props) {
  const [viewMode, setViewMode] = useState<"list" | "board">("list");
  const [listTab, setListTab] = useState<"hosts" | "groups">("hosts");
  const [statusCount, setStatusCount] = useState<{ online: number; total: number } | null>(null);
  // Стабильный колбэк: счётчик обновляем только при реальном изменении, иначе
  // setState → рендер → новая функция → бесконечный цикл у дочернего компонента.
  const handleStatusCount = useCallback((online: number, total: number) => {
    setStatusCount((prev) =>
      prev && prev.online === online && prev.total === total ? prev : {online, total}
    );
  }, []);

  return (
    <>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold">Хосты</h2>
          <p className="text-gray-500">Реестр управляемых узлов и добавление новых машин</p>
        </div>
        <div className="flex items-center border rounded-lg overflow-hidden shrink-0">
          <button
            className={`flex items-center gap-1.5 px-3 py-2 text-sm ${viewMode === "list" ? "bg-blue-600 text-white" : "text-gray-600 hover:bg-gray-100"}`}
            onClick={() => setViewMode("list")}
          >
            <List size={15}/>
            Список
          </button>
          <button
            className={`flex items-center gap-1.5 px-3 py-2 text-sm ${viewMode === "board" ? "bg-blue-600 text-white" : "text-gray-600 hover:bg-gray-100"}`}
            onClick={() => setViewMode("board")}
          >
            <LayoutGrid size={15}/>
            Доска
          </button>
        </div>
      </div>

      {viewMode === "board" && (
        <div style={{height: "calc(100vh - 180px)"}}>
          <HostBoardView hosts={hosts} onBoardsChange={onBoardsChange}/>
        </div>
      )}

      {viewMode === "list" && (
        <>
          {/* Вкладки + поиск + добавление — в одном ряду (как на странице истории):
              слева вкладки, по центру поиск, справа кнопка добавления */}
          <div className="flex items-center gap-4 border-gray-200 dark:border-gray-700">
            <div className="flex items-center gap-1 shrink-0 -mb-2">
              <button
                onClick={() => setListTab("hosts")}
                className={`px-4 py-2 text-sm font-semibold border-b-2 -mb-px transition-colors ${
                  listTab === "hosts" ? "border-blue-600 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700"
                }`}
              >
                Хосты
              </button>
              <button
                onClick={() => setListTab("groups")}
                className={`px-4 py-2 text-sm font-semibold border-b-2 -mb-px transition-colors ${
                  listTab === "groups" ? "border-blue-600 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700"
                }`}
              >
                Группы
              </button>
            </div>

            <div className="flex-1 flex justify-center gap-3">
              {/* Чип выбранной группы — как у выбора сценария: с крестиком для снятия */}
              {selectedGroupName && (
                <span
                  className="inline-flex items-center gap-1.5 pl-3 pr-1.5 py-1.5 rounded-full bg-blue-100 dark:bg-blue-950/50 text-sm font-medium text-blue-700 dark:text-blue-300 cursor-pointer hover:bg-blue-200 dark:hover:bg-blue-900/60 transition-colors"
                  onClick={onClearGroupFilter}
                  title="Убрать фильтр по группе"
                >
                  {selectedGroupName}
                  <button type="button" className="p-0.5 rounded-full hover:bg-blue-200 dark:hover:bg-blue-800" aria-label="Убрать фильтр">
                    <X size={14}/>
                  </button>
                </span>
              )}
              <div className="relative w-72">
                <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"/>
                <input className="input pl-9" placeholder="Поиск по имени" value={search}
                       onChange={(e) => onSearch(e.target.value)}/>
              </div>
              {/* Панель действий: проверка всех */}
              <div className="flex items-center justify-end">
                <button className="btn-secondary p-3" onClick={onCheckAll} disabled={checkingAll}>
                  <RefreshCw size={16} className={checkingAll ? "animate-spin" : ""}/>
                </button>
              </div>
            </div>

            {statusCount && listTab === "hosts" && (
              <span className="shrink-0 text-sm text-green-600 dark:text-green-400 font-medium">
                В сети: {statusCount.online} из {statusCount.total}
              </span>
            )}

            <button
              type="button"
              className="btn shrink-0"
              onClick={onAddHost}
            >
              <PlusIcon size={16}/>Добавить хост
            </button>
          </div>

          <div className="panel">
            {listTab === "hosts" && (
              <>
                {/* Живая сетка хостов: опрос сервера каждые 5 секунд, две секции
                    («В сети» / «Не в сети») и анимация затухание→смещение. */}
                <HostStatusGrid
                  hosts={filteredHosts}
                  selectionMode={selectionMode}
                  selectedIds={selectedIds}
                  onToggleSelect={onToggleSelect}
                  onInfoHost={onInfoHost}
                  onCount={handleStatusCount}
                />
              </>
            )}

            {listTab === "groups" && (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {groups.map((g) => {
                  const selected = selectedIds.has(g.id);
                  return (
                    <button
                      key={g.id}
                      className={`flex items-center gap-3 rounded-2xl bg-white dark:bg-gray-800 p-4 text-left transition-all duration-200 ${
                        selectionMode
                          ? `cursor-pointer border-4 ${
                            selected
                              ? "border-blue-600 hover:border-blue-500 hover:bg-blue-50 dark:hover:bg-blue-950"
                              : "border-gray-300 dark:border-gray-600 hover:border-blue-300 dark:hover:border-blue-700 hover:bg-blue-50 dark:hover:bg-gray-750"
                          }`
                          : "border-2 border-gray-200 dark:border-gray-700 hover:border-blue-300 dark:hover:border-blue-700"
                      }`}
                      onClick={() => {
                        // Выбор группы: применяем фильтр по ней и переключаемся
                        // на таб «Хосты» (фильтрацию делает родитель через groupFilter).
                        onSelectGroup(String(g.id));
                        setListTab("hosts");
                      }}
                      title="Информация"
                    >
                      {/*<span*/}
                      {/*  className={`w-2.5 h-2.5 rounded-full shrink-0 ${h.is_active ? "bg-green-500" : "bg-gray-400"}`}*/}
                      {/*  title={h.is_active ? "Активен" : "Недоступен"}*/}
                      {/*/>*/}
                      <div className="min-w-0 flex-1">
                        <div
                          className="font-semibold truncate flex flex-row gap-1">{g.name}
                          <div
                            className="text-xs text-gray-500 truncate mb-auto mt-auto">({g.hosts.length})
                          </div>
                        </div>
                        <div className="text-sm text-gray-500 dark:text-gray-400 truncate">
                          {(g.description !== "" && g.description !== null) ? g.description : "Описания нет"}
                        </div>
                      </div>
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        </>
      )}
    </>
  );
}