"use client";

import {Modal} from "@/components/Modal";
import type {Group, Host, SshKey} from "@/lib/host-types";

interface Props {
  host: Host;
  groups: Group[];
  keys: SshKey[];
  onClose: () => void;
  onSubmit: (fd: FormData, keyFile: File | null) => void;
}

/** Форма редактирования хоста. Stateless: не знает про API, отдаёт FormData наверх. */
export function EditHostModal({host, groups, keys, onClose, onSubmit}: Props) {
  return (
    <Modal title="Редактирование хоста" onClose={onClose}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const fileInput = e.currentTarget.querySelector<HTMLInputElement>('input[type="file"]');
          onSubmit(new FormData(e.currentTarget), fileInput?.files?.[0] || null);
        }}
        className="grid md:grid-cols-2 gap-4"
      >
        <input type="hidden" name="id" value={host.id}/>
        <label className="label">Имя хоста<input className="input" name="name" defaultValue={host.name}
                                                 required/></label>
        <label className="label">Пользователь<input className="input" name="username"
                                                    defaultValue={host.username} required/></label>
        <label className="label">IP-адрес<input className="input" name="address" defaultValue={host.address}
                                                required/></label>
        <label className="label">Порт<input className="input" name="port" type="number" defaultValue={host.port}
                                            required/></label>
        <label className="label">Кабинет<select className="input" name="group_id"
                                               defaultValue={host.group_id || ""}>
          <option value="">Без кабинета</option>
          {groups.map((g) => (<option key={g.id} value={g.id}>{g.name}</option>))}
        </select></label>
        <label className="label">SSH-ключ<select className="input" name="ssh_key_id"
                                                 defaultValue={host.ssh_key_id || ""}>
          <option value="">По умолчанию</option>
          {keys.map((k) => (<option key={k.id} value={k.id}>{k.name}</option>))}
        </select></label>
        <label className="label">Новый SSH-ключ<input type="file" className="input py-1.5"/></label>
        <label className="label">Пароль хоста<input className="input" name="password" type="password"/></label>
        <label className="label md:col-span-2">Описание<textarea className="input" name="description" rows={3}
                                                                 defaultValue={host.description || ""}/></label>
        <div className="flex gap-3 md:col-span-2">
          <button className="btn" type="submit">Сохранить</button>
          <button type="button" className="btn-secondary" onClick={onClose}>Отмена</button>
        </div>
      </form>
    </Modal>
  );
}