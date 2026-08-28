"use client";

import { ReactNode } from "react";
import { AlertTriangle } from "lucide-react";

/** Кастомное окно подтверждения — вместо системного confirm(), который нельзя
 *  оформить и который в профиле выглядит чужеродно. */
export function ConfirmDialog({
  title,
  children,
  confirmLabel = "Подтвердить",
  cancelLabel = "Отмена",
  danger = false,
  busy = false,
  onConfirm,
  onCancel,
  extraAction,
}: {
  title: string;
  children: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  /** Третья кнопка — например «Уйти без сохранения». */
  extraAction?: { label: string; onClick: () => void };
}) {
  return (
    <div
      className="fixed inset-0 z-[110] flex items-center justify-center bg-black/50 p-6 dark:bg-black/70"
      onClick={busy ? undefined : onCancel}
    >
      <div
        className="w-full max-w-md rounded-[14px] bg-white shadow-xl dark:bg-gray-800 dark:border dark:border-gray-700"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-3 border-b px-5 py-4 dark:border-gray-700">
          <AlertTriangle size={20} className={danger ? "text-red-500" : "text-amber-500"} />
          <h3 className="font-semibold dark:text-gray-200">{title}</h3>
        </div>
        <div className="px-5 py-4 text-sm text-gray-600 dark:text-gray-300">{children}</div>
        <div className="flex flex-wrap justify-end gap-2 border-t px-5 py-4 dark:border-gray-700">
          <button className="btn-secondary" onClick={onCancel} disabled={busy}>
            {cancelLabel}
          </button>
          {extraAction && (
            <button className="btn-secondary" onClick={extraAction.onClick} disabled={busy}>
              {extraAction.label}
            </button>
          )}
          <button className={danger ? "btn-danger" : "btn"} onClick={onConfirm} disabled={busy}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
