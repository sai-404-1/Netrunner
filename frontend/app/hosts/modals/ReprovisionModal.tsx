"use client";

import {Modal} from "@/components/Modal";
import type {Host, SshKey} from "@/lib/host-types";

interface Props {
  host: Host;
  keys: SshKey[];
  busy: boolean;
  onClose: () => void;
  onSubmit: (fd: FormData) => void;
}

/** Перепривязка SSH-ключа к одному хосту. Stateless: отдаёт FormData наверх. */
export function ReprovisionModal({host, keys, busy, onClose, onSubmit}: Props) {
  return (
    <Modal title="Перепривязка SSH-ключа" onClose={onClose}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit(new FormData(e.currentTarget));
        }}
        className="grid gap-4"
      >
        <p className="text-sm text-gray-500">Заново скопирует SSH-ключ на
          хост <b>{host.name}</b> ({host.username}@{host.address}).</p>
        <label className="label">
          SSH-ключ
          <select className="input" name="ssh_key_id" defaultValue={host.ssh_key_id || ""}>
            <option value="">По умолчанию</option>
            {keys.map((k) => (<option key={k.id} value={k.id}>{k.name}</option>))}
          </select>
        </label>
        <label className="label">Пароль хоста<input className="input" name="password" type="password"
                                                    placeholder="Оставьте пустым, чтобы использовать сохранённый"/></label>
        <div className="flex gap-3">
          <button className="btn" type="submit"
                  disabled={busy}>{busy ? "Привязка…" : "Привязать ключ"}</button>
          <button type="button" className="btn-secondary" onClick={onClose}>Отмена</button>
        </div>
      </form>
    </Modal>
  );
}