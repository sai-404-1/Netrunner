"use client";

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { ChevronRight } from "lucide-react";
import { apiGetClient } from "@/lib/api-client";
import type { Host } from "@/lib/host-types";

const POLL_MS = 5000;
const FADE_MS = 1000;
const MOVE_DELAY_MS = 500;
const MOVE_MS = 500;

interface Props {
  hosts: Host[];
  selectionMode: boolean;
  selectedIds: Set<number>;
  onToggleSelect: (id: number) => void;
  onInfoHost: (h: Host) => void;
}

interface RowProps {
  title: string;
  items: Host[];
  tone: "on" | "off";
  open: boolean;
  onToggle: () => void;
  innerRef: React.RefObject<HTMLDivElement | null>;
  emptyText: string;
  children: React.ReactNode;
}

// Объявлена на уровне модуля — иначе React перемонтирует секции на каждый рендер.
function Row({ title, items, tone, open, onToggle, innerRef, emptyText, children }: RowProps) {
  const dotColor = tone === "on" ? "bg-green-500" : "bg-gray-400";
  const countColor =
    tone === "on"
      ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
      : "bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400";

  return (
    <section>
      {/* Обёртка с -mx-5 растягивает border-b на всю ширину панели с обеих сторон.
          Кнопка внутри получает w-full и не нуждается в отрицательном margin. */}
      <div className="-mx-5 border-b border-gray-200 dark:border-gray-700">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center gap-2.5 px-5 py-3 text-sm text-left bg-transparent hover:bg-black/[.02] dark:hover:bg-white/[.03] transition-colors cursor-pointer"
      >
        <span className={`w-2 h-2 rounded-full shrink-0 ${dotColor}`} />
        <span className="font-semibold">{title}</span>
        <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${countColor}`}>{items.length}</span>

        <ChevronRight
          size={16}
          className={`ml-auto text-gray-400 transition-transform duration-300 ${open ? "rotate-90" : ""}`}
        />
      </button>
      </div>

      <div
        className={`overflow-hidden transition-[max-height] duration-400 ease-in-out ${open ? "max-h-[2000px]" : "max-h-0"}`}
      >
        {items.length === 0 ? (
          <p className="text-sm text-gray-400 py-2">{emptyText}</p>
        ) : (
          <div ref={innerRef} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 py-3">
            {children}
          </div>
        )}
      </div>
    </section>
  );
}

export function HostStatusGrid({ hosts, selectionMode, selectedIds, onToggleSelect, onInfoHost }: Props) {
  const [statuses, setStatuses] = useState<Host[] | null>(null);
  const statusFingerprintRef = useRef<string>("");
  const [userTouched, setUserTouched] = useState(false);
  const [openOnline, setOpenOnline] = useState(true);
  const [openOffline, setOpenOffline] = useState(false);

  const onlineRef = useRef<HTMLDivElement>(null);
  const offlineRef = useRef<HTMLDivElement>(null);
  const posRef = useRef<Map<number, { left: number; top: number }>>(new Map());

  const allowedIds = useMemo(() => new Set(hosts.map((h) => h.id)), [hosts]);

  useEffect(() => {
    let alive = true;
    async function poll() {
      try {
        const rows = await apiGetClient("/api/hosts/status");
        if (!alive || !Array.isArray(rows)) return;
        const filtered: Host[] = rows.filter((r: Host) => allowedIds.has(r.id));
        // Обновляем состояние только если статусы реально изменились —
        // иначе таймер вызывает FLIP-анимацию вхолостую и список прыгает.
        const fp = filtered.map((r) => `${r.id}:${r.is_active}`).join(",");
        if (fp !== statusFingerprintRef.current) {
          statusFingerprintRef.current = fp;
          setStatuses(filtered);
        }
      } catch {
        // тихий сбой — сетка остаётся в прежнем состоянии
      }
    }
    poll();
    const timer = setInterval(poll, POLL_MS);
    return () => { alive = false; clearInterval(timer); };
  }, [allowedIds]);

  const list = statuses ?? hosts;
  const online = useMemo(() => list.filter((h) => Boolean(h.is_active)), [list]);
  const offline = useMemo(() => list.filter((h) => !h.is_active), [list]);

  // Авто-раскрытие: пока пользователь не кликнул — открыта нужная секция.
  useEffect(() => {
    if (userTouched) return;
    if (online.length > 0) { setOpenOnline(true); setOpenOffline(false); }
    else { setOpenOnline(false); setOpenOffline(true); }
  }, [online.length, userTouched]);

  // FLIP: карточка затухает, затем плавно смещается в новую позицию.
  useLayoutEffect(() => {
    const containers = [onlineRef.current, offlineRef.current].filter(Boolean) as HTMLDivElement[];
    const nodes: { el: HTMLElement; id: number; next: { left: number; top: number } }[] = [];

    for (const c of containers) {
      c.querySelectorAll<HTMLElement>("[data-host-id]").forEach((el) => {
        const r = el.getBoundingClientRect();
        nodes.push({ el, id: Number(el.dataset.hostId), next: { left: r.left, top: r.top } });
      });
    }

    for (const { el, id, next } of nodes) {
      const prev = posRef.current.get(id);
      if (!prev) continue;
      const dx = prev.left - next.left;
      const dy = prev.top - next.top;
      if (!dx && !dy) continue;
      el.style.transition = "none";
      el.style.transform = `translate(${dx}px,${dy}px)`;
      requestAnimationFrame(() => {
        el.style.transition = `opacity ${FADE_MS}ms ease, background-color ${FADE_MS}ms ease, border-color ${FADE_MS}ms ease, transform ${MOVE_MS}ms cubic-bezier(.22,.61,.36,1) ${MOVE_DELAY_MS}ms`;
        el.style.transform = "translate(0,0)";
      });
    }

    const map = new Map<number, { left: number; top: number }>();
    for (const { id, next } of nodes) map.set(id, next);
    posRef.current = map;
  }, [online, offline]);

  function renderCard(h: Host) {
    const isOn = Boolean(h.is_active);
    const selected = selectedIds.has(h.id);

    let borderClass = isOn
      ? "border-gray-200 dark:border-gray-700 hover:border-blue-300 dark:hover:border-blue-600"
      : "border-gray-200 dark:border-gray-700";
    if (selectionMode) {
      borderClass = selected
        ? "border-brand ring-2 ring-brand/20"
        : "border-gray-300 dark:border-gray-600 hover:border-blue-300 dark:hover:border-blue-700";
    }

    return (
      <button
        key={h.id}
        data-host-id={h.id}
        onClick={() => selectionMode ? onToggleSelect(h.id) : onInfoHost(h)}
        className={`flex items-center gap-3 w-full px-3.5 py-3 text-left rounded-[10px] border bg-white dark:bg-gray-800 cursor-pointer will-change-transform transition-[opacity,background-color,border-color] ${isOn ? "" : "opacity-50"} ${borderClass}`}
        title={selectionMode ? (selected ? "Снять выбор" : "Выбрать") : "Открыть профиль"}
      >
        <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${isOn ? "bg-green-500" : "bg-gray-400"}`} />
        <span className="min-w-0 flex flex-col">
          <span className="font-semibold text-sm truncate">{h.name}</span>
          <span className="font-mono text-xs text-gray-500 dark:text-gray-400 truncate">{h.address}</span>
        </span>
      </button>
    );
  }

  return (
    <div className="flex flex-col gap-1.5">
      <Row
        title="В сети"
        items={online}
        tone="on"
        open={openOnline}
        onToggle={() => { setUserTouched(true); setOpenOnline((v) => !v); }}
        innerRef={onlineRef}
        emptyText="Нет машин в сети"
      >
        {online.map(renderCard)}
      </Row>
      <Row
        title="Не в сети"
        items={offline}
        tone="off"
        open={openOffline}
        onToggle={() => { setUserTouched(true); setOpenOffline((v) => !v); }}
        innerRef={offlineRef}
        emptyText="Все машины в сети"
      >
        {offline.map(renderCard)}
      </Row>
    </div>
  );
}
