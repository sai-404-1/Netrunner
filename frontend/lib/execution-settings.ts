// Настройка темпа выполнения сценариев — пакетами машин или скользящим
// параллелизмом. Значения и описание полей приходят с сервера
// (services/execution_settings.py), поэтому страница «Администрирование»
// может отрисовать форму по schema и не дублировать подписи и границы.

import { apiGetClient, apiPostClient } from "@/lib/api-client";

export type ExecutionMode = "parallel" | "batch";

/** От чьего имени выполняются SSH-команды на целевых машинах. */
export type SshUserMode = "service" | "primary";

export interface ExecutionConfig {
  /** Пользователь исполнения: service (netrunner-svc) либо primary (первичный хоста). */
  ssh_user_mode: SshUserMode;
  mode: ExecutionMode;
  /** Машин в пакете — сколько компьютеров работает одновременно в режиме batch. */
  batch_size: number;
  /** Пауза между пакетами, секунды. 0 — без паузы. */
  batch_delay: number;
  /** Потолок параллелизма, когда пакетный режим выключен. */
  max_parallel: number;
  /** Повторы запуска сценария, если он не смог начаться (coldawn). 0 — не повторять. */
  coldawn_retries: number;
}

export interface ExecutionFieldChoice {
  value: string;
  label: string;
}

/** Описание одного поля настройки — по нему строится форма. */
export interface ExecutionField {
  key: string;
  type: "int" | "choice";
  default: number | string;
  label: string;
  hint?: string;
  min?: number;
  max?: number;
  choices?: ExecutionFieldChoice[];
}

export type ExecutionSchema = Record<keyof ExecutionConfig, ExecutionField>;

export async function fetchExecutionSettings(): Promise<{
  config: ExecutionConfig;
  schema: ExecutionSchema;
}> {
  return apiGetClient("/api/admin/execution-settings");
}

/** Частичное обновление: отправляем только изменённые поля. */
export async function saveExecutionSettings(
  changes: Partial<ExecutionConfig>,
): Promise<{ config: ExecutionConfig }> {
  return apiPostClient("/api/admin/execution-settings", changes);
}
