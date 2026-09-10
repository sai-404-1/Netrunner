"use client";

import {Modal} from "@/components/Modal";

interface Props {
  onClose: () => void;
  onSubmit: (fd: FormData) => void;
}

/** Создание группы. Stateless: отдаёт FormData наверх. */
export function GroupCreateModal({onClose, onSubmit}: Props) {
  return (
    <Modal title="Создать кабинет" onClose={onClose}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit(new FormData(e.currentTarget));
        }}
        className="grid gap-4"
      >
        <label className="label">Название<input className="input" name="name" required/></label>
        <label className="label">Описание<textarea className="input" name="description" rows={3}/></label>
        <div className="flex gap-3">
          <button className="btn" type="submit">Создать</button>
          <button type="button" className="btn-secondary" onClick={onClose}>Отмена</button>
        </div>
      </form>
    </Modal>
  );
}