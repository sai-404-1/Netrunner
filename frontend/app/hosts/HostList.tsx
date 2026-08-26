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
  Trash2, LucideMonitorX,
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
  checkingAll: boolean;
  selectionMode: boolean;
  selectedIds: Set<number>;
  onSearch: (s: string) => void;
  onGroupFilter: (s: string) => void;
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
                           checkingAll,
                           selectionMode,
                           selectedIds,
                           onSearch,
                           onGroupFilter,
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
          <div className="panel">

            {/* Панель действий: выбор, поиск, фильтр, проверка — строкой */}
            <div className="flex flex-wrap items-center gap-3 mb-4">
              {/* Вкладки: Хосты / Группы */}
              <div className="flex justify-between panel p-1.5 items-center gap-1 border-gray-200 dark:border-gray-700">
                <button
                  onClick={() => setListTab("hosts")}
                  className={`px-2 py-1 btn-secondary text-sm font-semibold border-b-1 -mb-px transition-colors ${
                    listTab === "hosts" ? "border-blue-600 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700"
                  }`}
                >
                  Хосты
                </button>
                <button
                  onClick={() => setListTab("groups")}
                  className={`px-2 py-1 btn-secondary text-sm font-semibold border-b-1 -mb-px transition-colors ${
                    listTab === "groups" ? "border-blue-600 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700"
                  }`}
                >
                  Группы
                </button>
              </div>

              {/*<button className={selectionMode ? "btn" : "btn-secondary"} onClick={onToggleSelectionMode}>*/}
              {/*  <CheckSquare size={16}/>*/}
              {/*</button>*/}
              <div className="flex flex-row gap-3 ml-auto mr-auto ">
                <div className="relative">
                  <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"/>
                  <input className="input pl-9" placeholder="Поиск по имени" value={search}
                         onChange={(e) => onSearch(e.target.value)}/>
                </div>
                <button className="btn-secondary p-3" onClick={onCheckAll} disabled={checkingAll}>
                  <RefreshCw size={16} className={checkingAll ? "animate-spin" : ""}/>
                </button>
              </div>
              <button
                type="button"
                className="btn"
                onClick={onAddHost}
              >
                <PlusIcon size={16}/>Добавить хост
              </button>
            </div>

            {listTab === "hosts" && (
              <>
                {/* Сетка хостов: 1 колонка на телефоне, 2-3 на широких экранах.
            В режиме выбора клик по карточке переключает выделение — рамка
            утолщается (анимированно) и меняет цвет у выбранных карточек. */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
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
                    return (
                      <button
                        key={h.id}
                        className={`flex items-center gap-3 rounded-2xl bg-white dark:bg-gray-800 p-4 text-left transition-all duration-200 ${
                          selectionMode
                            ? `cursor-pointer border-4 ${
                              selected
                                ? "border-blue-600 hover:border-blue-500 hover:bg-blue-50 dark:hover:bg-blue-950"
                                : "border-gray-300 dark:border-gray-600 hover:border-blue-300 dark:hover:border-blue-700 hover:bg-blue-50 dark:hover:bg-gray-750"
                            }`
                            : "border-2 border-gray-200 dark:border-gray-700 hover:border-blue-300 dark:hover:border-blue-700"
                        }`}
                        onClick={(e) => {
                          if (selectionMode) {
                            onToggleSelect(h.id)
                          } else {
                            e.stopPropagation();
                            onInfoHost(h);
                          }
                        }}
                        title="Информация"
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
                      onClick={(e) => {
                        // if (selectionMode) {
                        //   onToggleSelect(h.id)
                        // } else {
                        //   e.stopPropagation();
                        //   onInfoHost(h);
                        // }
                        if (groupFilter === "none") {
                          hosts = hosts.filter((h) => !h.group_id);              // спец-значение "none" = без группы
                        } else if (groupFilter) {                              // выбрана конкретная группа
                          const group = groups.find((g) => String(g.id) === groupFilter);
                          if (group) {
                            const ids = group.hosts.map((h) => (typeof h === "number" ? h : h.id));
                            hosts = hosts.filter((h) => ids.includes(h.id));
                          }
                        }
                        onHosts(hosts)
                        setListTab("hosts")
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