"use client";

import { ReactElement, useEffect, useMemo, useState } from "react";
import { CheckCircle2, Circle, Loader2, MinusCircle, XCircle } from "lucide-react";
import { StatusBadge } from "@/components/Badge";
import { Module, RunHost, Scenario, ScenarioRun, ScenarioStepRun } from "@/lib/scenario-types";

/** Состояние шага/сценария на конкретном хосте. */
type HostState = "queued" | "running" | "done" | "failed" | "skipped";

const ICONS: Record<HostState, ReactElement> = {
  running: <Loader2 size={16} className="animate-spin text-blue-500 shrink-0" />,
  done: <CheckCircle2 size={16} className="text-green-500 shrink-0" />,
  failed: <XCircle size={16} className="text-red-500 shrink-0" />,
  skipped: <MinusCircle size={16} className="text-amber-500 shrink-0" />,
  queued: <Circle size={16} className="text-gray-400 shrink-0" />,
};

const LABELS: Record<HostState, string> = {
  running: "выполняется",
  done: "готово",
  failed: "ошибка",
  skipped: "пропущено",
  queued: "в очереди",
};

function isRunFinished(run: ScenarioRun): boolean {
  return run.status !== "running" && run.status !== "pending";
}

function stepState(sr: ScenarioStepRun | undefined, run: ScenarioRun): HostState {
  if (!sr) return isRunFinished(run) ? "skipped" : "queued";
  if (sr.status === "completed") return "done";
  if (sr.status === "failed") return "failed";
  if (sr.status === "skipped") return "skipped";
  return "running";
}

/** Итог сценария на одном хосте — по его собственным шагам, без оглядки на соседей. */
function scenarioStateForHost(run: ScenarioRun, hostId: number, stepIds: number[]): HostState {
  const states = stepIds.map((stepId) =>
    stepState(
      run.step_runs.find((r) => r.step_id === stepId && r.host_id === hostId),
      run,
    ),
  );
  if (states.length === 0) return "queued";
  if (states.every((s) => s === "queued")) return "queued";
  if (states.some((s) => s === "running" || s === "queued")) return "running";
  if (states.some((s) => s === "failed")) return "failed";
  if (states.some((s) => s === "skipped")) return "skipped";
  return "done";
}

/** Худшее из состояний хоста по всем сценариям очереди — для вкладки. */
function hostOverallState(states: HostState[]): HostState {
  if (states.some((s) => s === "running")) return "running";
  if (states.some((s) => s === "failed")) return "failed";
  if (states.some((s) => s === "skipped")) return "skipped";
  if (states.every((s) => s === "queued")) return "queued";
  return "done";
}

export default function RunExecution({
  runs,
  scenarios,
  modules,
}: {
  runs: ScenarioRun[];
  scenarios: Scenario[];
  modules: Module[];
}) {
  // Хосты собираем из целей запуска (приходят сразу) и из уже созданных
  // step_run — так вкладки видны ещё до первого выполненного шага.
  const hosts: RunHost[] = useMemo(() => {
    const map = new Map<number, string>();
    for (const run of runs) {
      for (const h of run.hosts || []) map.set(h.id, h.name);
      for (const sr of run.step_runs) {
        if (!map.has(sr.host_id)) map.set(sr.host_id, sr.host_name || `#${sr.host_id}`);
      }
    }
    return [...map].map(([id, name]) => ({ id, name })).sort((a, b) => a.name.localeCompare(b.name));
  }, [runs]);

  const [activeHostId, setActiveHostId] = useState<number | null>(null);

  useEffect(() => {
    if (hosts.length === 0) {
      setActiveHostId(null);
    } else if (activeHostId === null || !hosts.some((h) => h.id === activeHostId)) {
      setActiveHostId(hosts[0].id);
    }
  }, [hosts, activeHostId]);

  if (runs.length === 0 || hosts.length === 0) return null;

  const stepIdsOf = (run: ScenarioRun) =>
    (scenarios.find((s) => s.id === run.scenario_id)?.steps || [])
      .slice()
      .sort((a, b) => a.step_order - b.step_order);

  return (
    <div className="panel">
      <h3 className="font-semibold mb-3">Выполнение</h3>
      <p className="text-sm text-gray-500 mb-3">
        Каждый компьютер идёт по очереди сценариев сам по себе — вкладка показывает только его путь.
      </p>

      {/* Вкладки компьютеров */}
      <div className="flex flex-wrap gap-1 border-b dark:border-gray-700 mb-4">
        {hosts.map((host) => {
          const state = hostOverallState(
            runs.map((run) => scenarioStateForHost(run, host.id, stepIdsOf(run).map((s) => s.id))),
          );
          const active = host.id === activeHostId;
          return (
            <button
              key={host.id}
              type="button"
              onClick={() => setActiveHostId(host.id)}
              className={`flex items-center gap-2 px-3 py-2 text-sm rounded-t-md border-b-2 -mb-px transition-colors ${
                active
                  ? "border-blue-500 text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/40"
                  : "border-transparent text-gray-500 hover:bg-gray-50 dark:hover:bg-gray-800"
              }`}
            >
              {ICONS[state]}
              <span className="truncate max-w-[12rem]">{host.name}</span>
            </button>
          );
        })}
      </div>

      {/* Сценарии выбранного компьютера — в порядке очереди */}
      <div className="space-y-4">
        {activeHostId !== null &&
          runs.map((run) => {
            const steps = stepIdsOf(run);
            const state = scenarioStateForHost(run, activeHostId, steps.map((s) => s.id));
            return (
              <div key={run.id} className="rounded-lg border dark:border-gray-700">
                <div className="flex items-center justify-between gap-3 p-3 border-b dark:border-gray-700">
                  <span className="flex items-center gap-2 min-w-0">
                    {ICONS[state]}
                    <strong className="truncate">{run.scenario_name}</strong>
                  </span>
                  <span className="flex items-center gap-2 shrink-0">
                    <span className="text-xs text-gray-500">{LABELS[state]}</span>
                    <StatusBadge status={run.status} />
                  </span>
                </div>

                <div className="divide-y dark:divide-gray-700">
                  {steps.map((step) => {
                    const sr = run.step_runs.find(
                      (r) => r.step_id === step.id && r.host_id === activeHostId,
                    );
                    const st = stepState(sr, run);
                    const moduleName = modules.find((m) => m.id === step.module_id)?.name || "";
                    const output = sr?.output_text || "";
                    const error = sr?.error_text || "";
                    return (
                      <div key={step.id}>
                        <div className="flex items-center justify-between gap-3 px-3 py-2">
                          <span className="flex items-center gap-2 min-w-0">
                            {ICONS[st]}
                            <span className="truncate">
                              {step.step_order}. {step.step_name || moduleName}
                            </span>
                            {moduleName && (
                              <span className="text-gray-500 text-xs shrink-0">{moduleName}</span>
                            )}
                          </span>
                          <span className="text-xs text-gray-500 shrink-0">{LABELS[st]}</span>
                        </div>
                        {(output || error) && (
                          <details className="border-t dark:border-gray-700">
                            <summary className="px-3 py-2 text-xs text-gray-500 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 select-none">
                              Вывод шага
                            </summary>
                            <pre className="px-3 pb-3 text-xs bg-gray-50 dark:bg-gray-900 overflow-auto font-mono whitespace-pre-wrap">
                              {output}
                              {error ? `${output ? "\n" : ""}[ERR] ${error}` : ""}
                            </pre>
                          </details>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
      </div>
    </div>
  );
}
