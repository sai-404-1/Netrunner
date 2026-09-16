"use client";

import { useCallback, useEffect, useState } from "react";
import { AppWindow, Loader2, RefreshCw, X } from "lucide-react";
import { apiGetClient, apiPostClient } from "@/lib/api-client";
import { useToast } from "@/components/Toast";
import type { DesktopWindow } from "@/lib/host-types";

/** Открытые окна на рабочем столе машины: плитки с иконкой приложения,
 *  клик — закрыть. Список грузится по запросу (каждое обновление — SSH-заход
 *  на машину), без автоопроса. */
export function HostWindowsPanel({ hostId, online }: { hostId: number; online: boolean }) {
  const showToast = useToast();
  const [windows, setWindows] = useState<DesktopWindow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<DesktopWindow | null>(null);
  const [closing, setClosing] = useState(false);
  // Окно, которое мягко закрыть не вышло (приложение спросило «сохранить?»).
  const [stuck, setStuck] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiGetClient(`/api/hosts/${hostId}/windows`);
      setWindows(data.windows || []);
    } catch (err: any) {
      setWindows(null);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [hostId]);

  useEffect(() => {
    if (online) load();
  }, [online, load]);

  async function close(win: DesktopWindow, force: boolean) {
    setClosing(true);
    try {
      const res = await apiPostClient(`/api/hosts/${hostId}/windows/close`, { window_id: win.id, force });
      const title = win.title || win.wm_class;
      if (res.closed) {
        showToast(`Окно «${title}» закрыто`);
        setSelected(null);
        setStuck(null);
      } else {
        setStuck(win.id);
        showToast(`«${title}» не закрылось — приложение, скорее всего, спросило о сохранении`, "error");
      }
      await load();
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setClosing(false);
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold flex items-center gap-2">
          <AppWindow size={16} /> Открытые окна
        </h3>
        <button className="btn-secondary p-2" onClick={load} disabled={loading || !online} title="Обновить список">
          <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
        </button>
      </div>

      {!online ? (
        <p className="text-sm text-gray-500">Компьютер не в сети.</p>
      ) : error ? (
        <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
      ) : windows === null ? (
        <p className="text-sm text-gray-500 flex items-center gap-2">
          <Loader2 size={14} className="animate-spin" /> Получаем список окон…
        </p>
      ) : windows.length === 0 ? (
        <p className="text-sm text-gray-500">Открытых окон нет.</p>
      ) : (
        <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-6 gap-2">
          {windows.map((w) => {
            const isSelected = selected?.id === w.id;
            return (
              <button
                key={w.id}
                type="button"
                onClick={() => setSelected(isSelected ? null : w)}
                title={w.title || w.wm_class}
                className={`flex flex-col items-center gap-1.5 p-2 rounded-[10px] border text-center transition-colors ${
                  isSelected
                    ? "border-blue-600 bg-blue-50 dark:bg-blue-950/40"
                    : "border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800"
                }`}
              >
                {w.icon_png ? (
                  <img src={`data:image/png;base64,${w.icon_png}`} alt="" width={40} height={40} className="w-10 h-10" />
                ) : (
                  <AppWindow size={40} className="text-gray-400" />
                )}
                <span className="text-xs font-medium truncate w-full">{w.wm_class || "Окно"}</span>
                <span className="text-[11px] text-gray-500 truncate w-full">{w.title || "без заголовка"}</span>
              </button>
            );
          })}
        </div>
      )}

      {selected && (
        <div className="mt-3 p-3 rounded-[10px] border border-gray-200 dark:border-gray-700 flex flex-wrap items-center gap-2">
          <span className="text-sm flex-1 min-w-[10rem] truncate">
            {selected.title || selected.wm_class}
          </span>
          <button className="btn" onClick={() => close(selected, false)} disabled={closing}>
            <X size={16} /> Закрыть
          </button>
          {stuck === selected.id && (
            <button className="btn-danger" onClick={() => close(selected, true)} disabled={closing}>
              Закрыть принудительно
            </button>
          )}
        </div>
      )}
      {selected && stuck === selected.id && (
        <p className="text-xs text-gray-500 mt-2">
          Принудительное закрытие обрывает приложение — несохранённые данные ученика пропадут.
        </p>
      )}
    </div>
  );
}
