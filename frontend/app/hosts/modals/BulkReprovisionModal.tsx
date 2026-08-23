"use client";

import {Modal} from "@/components/Modal";
import type {SshKey} from "@/lib/host-types";

interface Props {
  count: number;
  keys: SshKey[];
  busy: boolean;
  onClose: () => void;
  onSubmit: (fd: FormData) => void;
}

/** Массовая перепривязка SSH-ключа для выбранных хостов. Stateless: отдаёт FormData наверх. */
export function BulkReprovisionModal({count, keys, busy, onClose, onSubmit}: Props) {
  return (
    <Modal title="Массовая перепривязка SSH-ключа" onClose={onClose}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit(new FormData(e.currentTarget));
        }}
        className="grid gap-4"
      >
        <p className="text-sm text-gray-500">
          Перепривязать SSH-ключ для <b>{count}</b> хостов.
        </p>
        <label className="label">
          SSH-ключ
          <select className="input" name="ssh_key_id">
            <option value="">Оставить текущий ключ каждого хоста</option>
            {keys.map((k) => (<option key={k.id} value={k.id}>{k.name}</option>))}
          </select>
        </label>
        <label className="label">Пароль хоста<input className="input" type="password" name="password"
                                                    placeholder="Для всех выбранных хостов"/></label>
        <div className="flex gap-3">
          <button className="btn" type="submit" disabled={busy}>
            {busy ? "Привязка…" : "Привязать для всех"}
          </button>
          <button type="button" className="btn-secondary" onClick={onClose}>Отмена
          </button>
        </div>
      </form>
    </Modal>
  );
}