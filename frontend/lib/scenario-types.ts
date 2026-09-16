
export interface Scenario {
  id: number;
  name: string;
  description: string | null;
  /** Папка сценария; null — лежит в корне. */
  folder_id: number | null;
  steps: ScenarioStep[];
  step_count: number;
  run_count: number;
}

export interface ScenarioFolder {
  id: number;
  name: string;
  scenario_count: number;
}

export interface ScenarioStep {
  id: number;
  module_id: number;
  step_order: number;
  step_name: string;
  config_json: string;
  on_failure: string;
}

export interface RunHost {
  id: number;
  name: string;
}

export interface ScenarioRun {
  id: number;
  scenario_id: number;
  scenario_name: string;
  target_type: string;
  target_id: number;
  status: string;
  started_at: string;
  finished_at: string | null;
  step_runs: ScenarioStepRun[];
  /** Хосты запуска — приходят только из /api/scenarios/runs/{id} */
  hosts?: RunHost[];
}

export interface ScenarioStepRun {
  id: number;
  step_id: number;
  host_id: number;
  host_name: string;
  module_id: number;
  /** completed | failed | skipped | running | pending */
  status: string;
  output_text: string | null;
  error_text: string | null;
  exit_code: number | null;
}

export interface Module {
  id: number;
  name: string;
  slug: string;
  supports_task_runner: boolean;
  schema_json?: string;
}

export interface SelectOption {
  value: string;
  label: string;
}

export interface Placeholder {
  name: string;
  label: string;
  default: string;
  type: string;
  options: SelectOption[];
}

export interface StepForm {
  module_id: string;
  module_slug: string;
  args: Record<string, string>;
  /** file_distribute: выбранные id загруженных файлов (массив, не строка!) */
  file_ids?: number[];
  on_failure: string;
}