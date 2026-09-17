// Типы страницы «Хосты» — вынесены из frontend/app/hosts/page.tsx.
// Нулевой вес в рантайме (стираются при компиляции), использовать `import type`.

export interface Host {
  id: number;
  name: string;
  username: string;
  address: string;
  port: number;
  is_active: boolean;
  last_seen?: string;
  group_id?: number;
  group_name?: string;
  ssh_key_id?: number;
  description?: string;
  /** ISO-время последнего снимка экрана (null — ещё не снят). Служит и
   *  cache-key для миниатюры: меняется — картинка перезапрашивается. */
  screenshot_captured_at?: string | null;
}

export interface Group {
  id: number;
  name: string;
  kind: string;
  description?: string;
  hosts: (number | Host)[];
}

export interface SshKey {
  id: number;
  name: string;
  key_type?: string;
  private_key_path?: string;
  public_key_path?: string;
  fingerprint?: string;
  public_key?: string;
  is_default?: boolean;
}
// --- Профиль хоста (/hosts/[id]) ---

/** Что роль пользователя позволяет делать с машиной — считает сервер. */
export interface HostPermissions {
  view: boolean;
  check: boolean;
  terminal: boolean;
  power: boolean;
  /** Просмотр и закрытие открытых окон на рабочем столе. */
  windows?: boolean;
  run_modules: boolean;
  edit: boolean;
  reprovision: boolean;
  delete: boolean;
}

export interface HostAgentInfo {
  status: string;
  last_seen_at?: string | null;
  ssh_username?: string;
}

export interface ProfileHost extends Host {
  ssh_key_name?: string | null;
  agent?: HostAgentInfo | null;
  created_at?: string;
}

export interface InventorySnapshot {
  id: number;
  hostname?: string | null;
  os_name?: string | null;
  kernel?: string | null;
  uptime_seconds?: number | null;
  cpu_model?: string | null;
  ram_mb?: number | null;
  disks_total_gb?: number | null;
  disks_free_gb?: number | null;
  disks_count?: number | null;
  current_user?: string | null;
  package_count?: number | null;
  collected_at: string;
}

export interface HostEvent {
  id: number;
  host_id: number;
  type: string;
  payload_json?: string | null;
  created_at: string;
}

export interface ProfileModule {
  id: number;
  name: string;
  slug: string;
  description?: string | null;
  schema_json?: string | null;
  admin_only: boolean;
}

export interface HostProfile {
  host: ProfileHost;
  inventory: InventorySnapshot | null;
  events: HostEvent[];
  permissions: HostPermissions;
  modules: ProfileModule[];
}

/** Одна метрика: проценты + занято/всего. Любое поле может быть null —
 *  источника на машине может не быть (нет GPU, нет swap). */
export interface MetricPair {
  used_mb: number | null;
  total_mb: number | null;
  percent: number | null;
}

export interface HostMetrics {
  available: boolean;
  error?: string;
  cpu?: { percent: number | null; cores: number | null; load: string | null };
  ram?: MetricPair;
  swap?: MetricPair;
  disk?: { used_gb: number | null; total_gb: number | null; percent: number | null };
  gpu?: {
    name: string;
    percent: number | null;
    vram_used_mb: number | null;
    vram_total_mb: number | null;
    vram_percent: number | null;
  } | null;
  uptime_seconds?: number | null;
  hostname?: string | null;
}

/** Окно приложения на рабочем столе машины (см. services/desktop_windows_helper.py). */
export interface DesktopWindow {
  id: number;
  title: string;
  wm_class: string;
  wm_instance: string;
  pid: number | null;
  width: number;
  height: number;
  /** PNG иконки приложения в base64 или null, если приложение её не отдаёт. */
  icon_png: string | null;
}
