export interface Scenario {
  id: number;
  name: string;
  step_count?: number;
}

export interface Host {
  id: number;
  name: string;
}

export interface Group {
  id: number;
  name: string;
}

export interface ScheduledTask {
  id: number;
  name: string;
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
}
