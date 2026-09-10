"use client";

import {useState} from "react";
import {
  RefreshCw,
  Search,
  CheckSquare,
  PlusIcon,
  List,
  LayoutGrid,
  Pencil,
  Trash2, X, LucideMonitorX,
} from "lucide-react";
import {DataTable} from "@/components/DataTable";
import {HostBoardView} from "@/components/HostBoardView";
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
  /** Активная вкладка списка: «Кабинеты» (groups) или «Хосты» (hosts).
   *  Держится в родителе, чтобы выбор переживал уход на профиль хоста и возврат. */
  listTab: "hosts" | "groups";
  onListTab: (tab: "hosts" | "groups") => void;
  /** Режим выбора цели для запуска: список подсвечен, клик по карточке выбирает цель. */
  pickMode: boolean;
  /** id выбранной цели (строкой) — карточка подсвечивается фоном, как выбранный сценарий. */
  pickedId: string | null;
  onPickTarget: (id: string) => void;
  /** Блок запуска задачи — рендерится сразу под строкой вкладок/поиска/добавления. */
  runPanel?: React.ReactNode;
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
                           listTab,
                           onListTab,
                           pickMode,
                           pickedId,
                           onPickTarget,
                           runPanel,
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
              {/* Порядок вкладок: сначала «Кабинеты», затем «Хосты» (по просьбе Сая).
                  Клик по вкладке выбирает и тип цели для запуска (см. блок запуска). */}
              <button
                onClick={() => onListTab("groups")}
                className={`px-4 py-2 text-sm font-semibold border-b-2 -mb-px transition-colors ${
                  listTab === "groups" ? "border-blue-600 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700"
                }`}
              >
                Кабинеты
              </button>
              <button
                onClick={() => onListTab("hosts")}
                className={`px-4 py-2 text-sm font-semibold border-b-2 -mb-px transition-colors ${
                  listTab === "hosts" ? "border-blue-600 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700"
                }`}
              >
                Хосты
              </button>
            </div>

            <div className="flex-1 flex justify-center gap-3">
              {/* Чип выбранного кабинета-фильтра — в стиле выбранного сценария
                  (менее округлый, чем прежняя «пилюля» rounded-full). */}
              {selectedGroupName && (
                <span
                  className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 text-sm cursor-pointer hover:bg-red-50 hover:border-red-300 dark:hover:bg-red-950/40 dark:hover:border-red-700 transition-colors"
                  onClick={onClearGroupFilter}
                  title="Убрать фильтр по кабинету"
                >
                  {selectedGroupName}
                  <button type="button" className="text-gray-400 hover:text-red-500 shrink-0" aria-label="Убрать фильтр">
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

            <button
              type="button"
              className="btn shrink-0"
              onClick={onAddHost}
            >
              <PlusIcon size={16}/>Добавить хост
            </button>
          </div>

          {/* Блок запуска задачи — перенесён со страницы «Запуск задачи» (пункт
              убран из сайдбара) и стоит сразу под строкой вкладок/поиска/добавления. */}
          {runPanel}

          <div className="panel">
            {listTab === "hosts" && (
              <>
                {/* Сетка хостов: 1 колонка на телефоне, 2-3 на широких экранах.
            В режиме выбора клик по карточке переключает выделение — рамка
            утолщается (анимированно) и меняет цвет у выбранных карточек. */}
                <div className={`grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 rounded-2xl ${
                  pickMode ? "ring-2 ring-blue-300 dark:ring-blue-700 p-2" : ""
                }`}>
                  {filteredHosts.length === 0 && (
                    <div className="col-span-full m-auto text-gray-500 dark:text-gray-400 py-8">
                      <>
                        <LucideMonitorX size={48} className="m-auto"/>
                        <h4>404: хосты не найдены</h4>
                      </>
                    </div>
                  )}
                  {filteredHosts.map((h) => {
                    const selected = selectedIds.has(h.id);
                    const picked = pickMode && pickedId === String(h.id);
                    return (
                      <button
                        key={h.id}
                        className={`flex items-center gap-3 rounded-2xl bg-white dark:bg-gray-800 p-4 text-left transition-all duration-200 ${
                          pickMode
                            ? `cursor-pointer border-4 ${
                              picked
                                ? "border-blue-600 bg-blue-50 dark:bg-blue-950/40"
                                : "border-gray-300 dark:border-gray-600 hover:border-blue-300 dark:hover:border-blue-700 hover:bg-blue-50 dark:hover:bg-gray-750"
                            }`
                            : selectionMode
                            ? `cursor-pointer border-4 ${
                              selected
                                ? "border-blue-600 hover:border-blue-500 hover:bg-blue-50 dark:hover:bg-blue-950"
                                : "border-gray-300 dark:border-gray-600 hover:border-blue-300 dark:hover:border-blue-700 hover:bg-blue-50 dark:hover:bg-gray-750"
                            }`
                            : "border-2 border-gray-200 dark:border-gray-700 hover:border-blue-300 dark:hover:border-blue-700"
                        }`}
                        onClick={(e) => {
                          if (pickMode) {
                            onPickTarget(String(h.id));
                          } else if (selectionMode) {
                            onToggleSelect(h.id)
                          } else {
                            e.stopPropagation();
                            onInfoHost(h);
                          }
                        }}
                        title={pickMode ? "Выбрать целью" : "Информация"}
                      >
                <span
                  className={`w-2.5 h-2.5 rounded-full shrink-0 ${h.is_active ? "bg-green-500" : "bg-gray-400"}`}
                  title={h.is_active ? "Активен" : "Недоступен"}
                />
                        <div className="min-w-0 flex-1">
                          <div
                            className={`font-semibold truncate ${h.is_active ? "gray" : "text-gray-500"}`}>{h.name}</div>
                          <div className="text-sm text-gray-500 dark:text-gray-400 truncate">{h.address}</div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </>
            )}

            {listTab === "groups" && (
              <div className={`grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 rounded-2xl ${
                pickMode ? "ring-2 ring-blue-300 dark:ring-blue-700 p-2" : ""
              }`}>
                {groups.map((g) => {
                  const selected = selectedIds.has(g.id);
                  const picked = pickMode && pickedId === String(g.id);
                  return (
                    <button
                      key={g.id}
                      className={`flex items-center gap-3 rounded-2xl bg-white dark:bg-gray-800 p-4 text-left transition-all duration-200 ${
                        pickMode
                          ? `cursor-pointer border-4 ${
                            picked
                              ? "border-blue-600 bg-blue-50 dark:bg-blue-950/40"
                              : "border-gray-300 dark:border-gray-600 hover:border-blue-300 dark:hover:border-blue-700 hover:bg-blue-50 dark:hover:bg-gray-750"
                          }`
                          : selectionMode
                          ? `cursor-pointer border-4 ${
                            selected
                              ? "border-blue-600 hover:border-blue-500 hover:bg-blue-50 dark:hover:bg-blue-950"
                              : "border-gray-300 dark:border-gray-600 hover:border-blue-300 dark:hover:border-blue-700 hover:bg-blue-50 dark:hover:bg-gray-750"
                          }`
                          : "border-2 border-gray-200 dark:border-gray-700 hover:border-blue-300 dark:hover:border-blue-700"
                      }`}
                      onClick={() => {
                        if (pickMode) {
                          // Режим выбора цели: клик по кабинету выбирает его целью запуска.
                          onPickTarget(String(g.id));
                          return;
                        }
                        // Обычный режим: применяем фильтр по кабинету и переходим
                        // на вкладку «Хосты» (фильтрацию делает родитель через groupFilter).
                        onSelectGroup(String(g.id));
                        onListTab("hosts");
                      }}
                      title={pickMode ? "Выбрать целью" : "Информация"}
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