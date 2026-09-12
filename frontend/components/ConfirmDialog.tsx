"use client";

import { Modal } from "@/components/Modal";

/** Кастомный диалог подтверждения (вместо window.confirm). */
export function ConfirmDialog({
  title,
  message,
  confirmLabel = "Удалить",
  cancelLabel = "Отмена",
  onConfirm,
  onClose,
  danger = true,
}: {
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onClose: () => void;
  danger?: boolean;
}) {
  return (
    <Modal title={title} onClose={onClose} size="sm">
      <p className="text-gray-700 dark:text-gray-300">{message}</p>
      <div className="flex justify-end gap-3 mt-5">
        <button type="button" className="btn-secondary" onClick={onClose}>{cancelLabel}</button>
        <button
          type="button"
          className={danger ? "btn-danger" : "btn"}
          onClick={() => { onConfirm(); onClose(); }}
        >
          {confirmLabel}
        </button>
      </div>
    </Modal>
  );
}
