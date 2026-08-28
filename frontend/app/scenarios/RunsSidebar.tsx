"use client";

import { Eye, Loader2, RefreshCw } from "lucide-react";
import { StatusBadge } from "@/components/Badge";
import { formatDate } from "@/lib/utils";
import type { ScenarioRun } from "@/lib/scenario-types";

function isActive(run: ScenarioRun): boolean {
  return run.status === "running" || run.status === "pending";
}

/** Сколько машин уже упомянуто в запуске — по step_run'ам, они появляются
 *  по мере того, как хосты доходят до шагов. */
function hostCount(run: ScenarioRun): number {
  return new Set(run.step_runs.map((r) => r.host_id)).size;
}

function RunRow({
  run,
  watched,
  onWatch,
}: {
  run: ScenarioRun;
  watched: boolean;
  onWatch: (id: number) => void;
}) {
  const hosts = hostCount(run);
  return (
    <button
      type="button"
      onClick={() => onWatch(run.id)}
      className={`w-full text-left rounded-[10px] border p-2.5 transition-colors ${
        watched
          ? "border-blue-500 bg-blue-50 dark:bg-blue-950/40"
          : "border-gray-200 dark:border-gray-700 hover:border-blue-300 dark:hover:border-blue-700"
      }`}
    >
      <div className="flex items-center gap-2 min-w-0">
        {isActive(run) && <Loader2 size={14} className="animate-spin text-blue-500 shrink-0" />}
        <span className="font-semibold truncate flex-1">{run.scenario_name}</span>
        <StatusBadge status={run.status} />
      </div>
      <div className="flex items-center justify-between gap-2 mt-1 text-xs text-gray-500">
        <span className="truncate">
          #{run.id} · {formatDate(run.started_at)}
        </span>
        <span className="shrink-0 flex items-center gap-1">
          {hosts > 0 && `${hosts} маш.`}
          {watched ? (
            <span className="text-blue-600 dark:text-blue-400 font-semibold">смотрю</span>
          ) : (
            <Eye size={13} className="opacity-60" />
          )}
        </span>
      </div>
    </button>
  );
}

/** Правая колонка страницы сценариев: сверху то, что выполняется прямо сейчас
 *  (к любому запуску можно подключиться и смотреть вывод), под ним — история
 *  всех запусков. */
export default function RunsSidebar({
  runs,
  watchedIds,
  onWatch,
  onRefresh,
  refreshing = false,
}: {
  runs: ScenarioRun[];
  watchedIds: number[];
  onWatch: (id: number) => void;
  onRefresh: () => void;
  refreshing?: boolean;
}) {
  const active = runs.filter(isActive);
  const finished = runs.filter((r) => !isActive(r));
  const watched = new Set(watchedIds);

  return (
    <div className="panel space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">Запуски</h3>
        <button
          type="button"
          className="btn-secondary p-2"
          onClick={onRefresh}
          title="Обновить список"
        >
          <RefreshCw size={14} className={refreshing ? "animate-spin" : ""} />
        </button>
      </div>

      <div>
        <h4 className="text-xs font-bold uppercase tracking-wide text-gray-500 mb-2">
          Выполняются сейчас
        </h4>
        {active.length === 0 ? (
          <p className="text-sm text-gray-500">Сейчас ничего не выполняется.</p>
        ) : (
          <div className="space-y-2">
            {active.map((run) => (
              <RunRow key={run.id} run={run} watched={watched.has(run.id)} onWatch={onWatch} />
            ))}
          </div>
        )}
      </div>

      <div className="pt-3 border-t dark:border-gray-700">
        <h4 className="text-xs font-bold uppercase tracking-wide text-gray-500 mb-2">
          История
        </h4>
        {finished.length === 0 ? (
          <p className="text-sm text-gray-500">Завершённых запусков пока нет.</p>
        ) : (
          <div className="space-y-2 max-h-[32rem] overflow-auto pr-1">
            {finished.map((run) => (
              <RunRow key={run.id} run={run} watched={watched.has(run.id)} onWatch={onWatch} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
