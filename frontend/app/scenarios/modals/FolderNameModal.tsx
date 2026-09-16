"use client";

import { useState } from "react";
import { Modal } from "@/components/Modal";

/** Ввод имени папки сценариев — создание и переименование. */
export function FolderNameModal({
  title,
  initialName = "",
  confirmLabel,
  onSubmit,
  onClose,
}: {
  title: string;
  initialName?: string;
  confirmLabel: string;
  onSubmit: (name: string) => void;
  onClose: () => void;
}) {
  const [name, setName] = useState(initialName);
  const trimmed = name.trim();

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!trimmed) return;
    onSubmit(trimmed);
    onClose();
  };

  return (
    <Modal title={title} onClose={onClose} size="sm">
      <form onSubmit={submit}>
        <label className="block text-sm mb-1">Название папки</label>
        <input
          className="input w-full"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Например: Онлайн"
          autoFocus
        />
        <div className="flex justify-end gap-3 mt-5">
          <button type="button" className="btn-secondary" onClick={onClose}>Отмена</button>
          <button type="submit" className="btn" disabled={!trimmed}>{confirmLabel}</button>
        </div>
      </form>
    </Modal>
  );
}
