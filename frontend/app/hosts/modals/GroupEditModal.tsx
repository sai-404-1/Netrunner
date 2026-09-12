"use client";

import {Modal} from "@/components/Modal";
import type {Group} from "@/lib/host-types";

interface Props {
  group: Group;
  onClose: () => void;
  onSubmit: (fd: FormData) => void;
}

/** Редактирование группы. Stateless: отдаёт FormData наверх. */
export function GroupEditModal({group, onClose, onSubmit}: Props) {
  return (
    <Modal title="Редактирование кабинета" onClose={onClose}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit(new FormData(e.currentTarget));
        }}
        className="grid gap-4"
      >
        <input type="hidden" name="id" value={group.id}/>
        <label className="label">Название<input className="input" name="name" defaultValue={group.name}
                                                required/></label>
        <label className="label">Описание<textarea className="input" name="description" rows={3}
                                                   defaultValue={group.description || ""}/></label>
        <div className="flex gap-3">
          <button className="btn" type="submit">Сохранить</button>
          <button type="button" className="btn-secondary" onClick={onClose}>Отмена</button>
        </div>
      </form>
    </Modal>
  );
}