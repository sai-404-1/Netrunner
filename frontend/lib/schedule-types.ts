export interface Template {
  id: number;
  name: string;
  module_id: number;
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
  template_id: number;
  target_type: "host" | "group";
  target_id: number;
  run_at: string;
  is_enabled: boolean;
}