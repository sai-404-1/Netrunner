export interface Scenario {
  id: number;
  name: string;
  step_count?: number;
  description?: string;
}

export interface Host {
  id: number;
  name: string;
  is_active?: boolean;
  address?: string;
}

export interface Group {
  id: number;
  name: string;
}

export interface ScheduledTask {
  id: number;
  name: string;
  description?: string | null;
  scenario_id: number | null;
  target_type: "host" | "group";
  target_id: number;
  run_at: string;
  is_enabled: boolean;
  last_run_at?: string | null;
  interval_seconds?: number | null;
  max_runs?: number | null;
  run_count?: number;
  wait_for_online?: boolean;
  days_of_week?: string;
  start_min?: number | null;
  end_min?: number | null;
  interval_min?: number | null;
  // Мульти-выбор цели/сценариев (JSON-строки из БД)
  target_host_ids_json?: string | null;
  target_group_ids_json?: string | null;
  scenario_ids_json?: string | null;
}

/** Разобрать JSON-строку списка id в массив чисел. */
export function parseIdList(str?: string | null): number[] {
  if (!str) return [];
  try {
    const v = JSON.parse(str);
    return Array.isArray(v) ? v.map(Number) : [];
  } catch {
    return [];
  }
}

/** Все сценарии задачи (мульти или одиночный). */
export function taskScenarioIds(t: ScheduledTask): number[] {
  const multi = parseIdList(t.scenario_ids_json);
  if (multi.length) return multi;
  return t.scenario_id ? [t.scenario_id] : [];
}

/** (hostIds, groupIds) цели задачи (мульти или legacy-поля). */
export function taskTargetIds(t: ScheduledTask): [number[], number[]] {
  const hosts = parseIdList(t.target_host_ids_json);
  const groups = parseIdList(t.target_group_ids_json);
  if (hosts.length || groups.length) return [hosts, groups];
  if (t.target_type === "group" && t.target_id) return [[], [t.target_id]];
  if (t.target_id) return [[t.target_id], []];
  return [[], []];
}
