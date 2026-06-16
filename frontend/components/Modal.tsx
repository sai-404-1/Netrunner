"use client";

import { ReactNode } from "react";
import { X, Copy, Download } from "lucide-react";
import { useToast } from "@/components/Toast";

export function Modal({
  title,
  children,
  onClose,
  size = "md",
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  size?: "sm" | "md" | "lg" | "xl";
}) {
  const sizeClass = {
    sm: "max-w-md",
    md: "max-w-2xl",
    lg: "max-w-4xl",
    xl: "max-w-6xl",
  }[size];

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 p-6" onClick={onClose}>
      <div
        className={`flex flex-col max-h-[90vh] w-full ${sizeClass} rounded-[14px] bg-white shadow-xl overflow-hidden`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b px-5 py-4">
          <h3 className="font-semibold">{title}</h3>
          <button onClick={onClose} className="btn-secondary p-2">
            <X size={18} />
          </button>
        </div>
        <div className="flex-1 overflow-auto p-5">{children}</div>
      </div>
    </div>
  );
}

export function OutputModal({
  text,
  title,
  onClose,
}: {
  text: string;
  title: string;
  onClose: () => void;
}) {
  const showToast = useToast();

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      showToast("Скопировано в буфер обмена");
    } catch {
      showToast("Не удалось скопировать", "error");
    }
  }

  function download() {
    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "report.txt";
    a.click();
    URL.revokeObjectURL(url);
    showToast("Отчёт сохранён");
  }

  return (
    <Modal title={title} onClose={onClose} size="xl">
      <div className="flex gap-2 mb-3">
        <button onClick={copy} className="btn-secondary py-1.5 px-3 text-sm">
          <Copy size={16} /> Копировать
        </button>
        <button onClick={download} className="btn-secondary py-1.5 px-3 text-sm">
          <Download size={16} /> Сохранить
        </button>
      </div>
      <pre className="bg-slate-950 text-gray-200 rounded-[10px] p-4 text-sm h-[60vh] overflow-auto">{text}</pre>
    </Modal>
  );
}
