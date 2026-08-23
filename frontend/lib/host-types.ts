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