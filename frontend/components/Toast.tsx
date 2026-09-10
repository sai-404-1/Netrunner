"use client";

import { createContext, useContext, useState, useCallback, ReactNode } from "react";

interface Toast {
  id: number;
  message: string;
  type?: "ok" | "error";
  /** Уведомление в фазе исчезновения — проигрывается toast-out, потом удаляется. */
  leaving?: boolean;
}

interface ToastContextType {
  showToast: (message: string, type?: "ok" | "error") => void;
}

const ToastContext = createContext<ToastContextType | null>(null);

// Сколько уведомление висит и сколько длится анимация ухода (см. globals.css: toast-out).
const TOAST_TTL_MS = 3200;
const TOAST_EXIT_MS = 220;

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx.showToast;
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const dismiss = useCallback((id: number) => {
    // Сначала анимация исчезновения, затем удаление из списка.
    setToasts((prev) => prev.map((t) => (t.id === id ? { ...t, leaving: true } : t)));
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, TOAST_EXIT_MS);
  }, []);

  const showToast = useCallback((message: string, type: "ok" | "error" = "ok") => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => dismiss(id), TOAST_TTL_MS);
  }, [dismiss]);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div className="fixed bottom-5 right-5 z-50 flex flex-col gap-2 overflow-hidden">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`max-w-md rounded-2xl px-4 py-3 text-sm text-white shadow-lg ${
              t.type === "error" ? "bg-red-600" : "bg-slate-900"
            } ${t.leaving ? "toast-out" : "toast-in"}`}
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
