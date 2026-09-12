"use client";

import {useEffect, useLayoutEffect, useMemo, useRef, useState} from "react";
import {apiGetClient} from "@/lib/api-client";
import type {Host} from "@/lib/host-types";

/** Интервал опроса сервера (мс) — список берётся из базы, без перепинга. */
const POLL_MS = 5000;
/** Длительность затухания карточки (мс). */
const FADE_MS = 1000;
/** Задержка перед смещением — «на середине затухания» (мс). */
const MOVE_DELAY_MS = 500;
/** Длительность самого смещения (мс). */
const MOVE_MS = 500;

interface Props {
  /** Отфильтрованный родителем список (поиск/группа) — задаёт допустимые id. */
  hosts: Host[];
  selectionMode: boolean;
  selectedIds: Set<number>;
  onToggleSelect: (id: number) => void;
  onInfoHost: (h: Host) => void;
  /** Родитель показывает счётчик на уровне шапки. Должен быть стабильным (useCallback). */
  onCount?: (online: number, total: number) => void;
}

interface RowProps {
  title: string;
  items: Host[];
  open: boolean;
  toggle: () => void;
  innerRef: React.RefObject<HTMLDivElement | null>;
  tone: "on" | "off";
  emptyText: string;
  renderCard: (h: Host) => React.ReactNode;
}

/** Горизонтальная полоса-«вкладка»: заголовок на всю ширину + раскрываемый список.
 *  Объявлена на уровне модуля (не внутри HostStatusGrid) — иначе React считает
 *  её новым типом на каждый рендер и перемонтирует секции. */
function Row({title, items, open, toggle, innerRef, tone, emptyText, renderCard}: RowProps) {
  return (
    <section className="nr-row">
      <button
        type="button"
        className={`nr-row-head nr-row-head-${tone} ${open ? "nr-head-open" : ""}`}
        onClick={toggle}
      >
        <span className={`nr-row-dot nr-row-dot-${tone}`}/>
        <span className="nr-row-title">{title}</span>
        <span className={`nr-row-count nr-row-count-${tone}`}>{items.length}</span>
        <span className="nr-row-chev">›</span>
      </button>
      <div className="nr-row-body">
        <div className="nr-row-inner">
          {items.length === 0 ? (
            <div className="nr-empty">{emptyText}</div>
          ) : (
            <div ref={innerRef} className="nr-grid">
              {items.map(renderCard)}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

/**
 * Живая сетка хостов: каждые 5 секунд опрашивает сервер и делит машины на две
 * горизонтальные полосы-«вкладки» («В сети» / «Не в сети»), растянутые на всю
 * ширину и раскрываемые кликом. Пропавшая машина не исчезает — сначала затухает
 * в серый, затем смещается в свою полосу (FLIP).
 */
export function HostStatusGrid({
                                hosts,
                                selectionMode,
                                selectedIds,
                                onToggleSelect,
                                onInfoHost,
                                onCount,
                              }: Props) {
  const [statuses, setStatuses] = useState<Host[] | null>(null);
  // Авто-раскрытие: пока пользователь не кликнул сам — открыта та, где есть машины.
  const [userTouched, setUserTouched] = useState(false);
  const [openOnline, setOpenOnline] = useState(true);
  const [openOffline, setOpenOffline] = useState(false);

  const onlineRef = useRef<HTMLDivElement>(null);
  const offlineRef = useRef<HTMLDivElement>(null);
  const posRef = useRef<Map<number, { left: number; top: number }>>(new Map());

  // Допустимые id — то, что прошло поиск/фильтр группы у родителя.
  const allowedIds = useMemo(() => new Set(hosts.map((h) => h.id)), [hosts]);

  useEffect(() => {
    let alive = true;
    async function poll() {
      try {
        const rows = await apiGetClient("/api/hosts/status");
        if (!alive || !Array.isArray(rows)) return;
        setStatuses(rows.filter((r: Host) => allowedIds.has(r.id)));
      } catch {
        // тихий сбой опроса — сетка остаётся в прежнем состоянии
      }
    }
    poll();
    const pollTimer = setInterval(poll, POLL_MS);
    return () => {
      alive = false;
      clearInterval(pollTimer);
    };
  }, [allowedIds]);

  // Разделение на полосы. Порядок внутри — как пришёл (живые впереди).
  const list = statuses ?? hosts;
  const online = useMemo(() => list.filter((h) => Boolean(h.is_active)), [list]);
  const offline = useMemo(() => list.filter((h) => !h.is_active), [list]);

  // Отдаём счётчик наверх. onCount должен быть стабильным (useCallback у родителя),
  // иначе этот эффект зациклится: setState у родителя → новый onCount → эффект…
  useEffect(() => {
    onCount?.(online.length, list.length);
  }, [online.length, list.length, onCount]);

  // Авто-раскрытие: есть живые — «В сети»; живых нет — «Не в сети».
  useEffect(() => {
    if (userTouched) return;
    if (online.length > 0) {
      setOpenOnline(true);
      setOpenOffline(false);
    } else {
      setOpenOnline(false);
      setOpenOffline(true);
    }
  }, [online.length, userTouched]);

  // FLIP: затухание идёт сразу, смещение — с задержкой (после затухания).
  useLayoutEffect(() => {
    const containers = [onlineRef.current, offlineRef.current].filter(Boolean) as HTMLDivElement[];
    const nodes: { el: HTMLElement; id: number; next: { left: number; top: number } }[] = [];

    for (const c of containers) {
      c.querySelectorAll<HTMLElement>("[data-host-id]").forEach((el) => {
        const r = el.getBoundingClientRect();
        nodes.push({el, id: Number(el.dataset.hostId), next: {left: r.left, top: r.top}});
      });
    }

    for (const {el, id, next} of nodes) {
      const prev = posRef.current.get(id);
      if (!prev) continue;
      const dx = prev.left - next.left;
      const dy = prev.top - next.top;
      if (!dx && !dy) continue;
      el.style.transition = "none";
      el.style.transform = `translate(${dx}px, ${dy}px)`;
      requestAnimationFrame(() => {
        el.style.transition =
          `opacity ${FADE_MS}ms ease, background-color ${FADE_MS}ms ease, border-color ${FADE_MS}ms ease,` +
          ` transform ${MOVE_MS}ms cubic-bezier(.22,.61,.36,1) ${MOVE_DELAY_MS}ms`;
        el.style.transform = "translate(0px, 0px)";
      });
    }

    const map = new Map<number, { left: number; top: number }>();
    for (const {id, next} of nodes) map.set(id, next);
    posRef.current = map;
  }, [online, offline]);

  function renderCard(h: Host) {
    const selected = selectedIds.has(h.id);
    const isOn = Boolean(h.is_active);
    return (
      <button
        key={h.id}
        data-host-id={h.id}
        className={`nr-card ${isOn ? "nr-on" : "nr-off"} ${
          selectionMode ? (selected ? "nr-sel" : "nr-unsel") : ""
        }`}
        onClick={(e) => {
          if (selectionMode) {
            onToggleSelect(h.id);
          } else {
            e.stopPropagation();
            onInfoHost(h);
          }
        }}
        title="Информация"
      >
        <span className="nr-dot"/>
        <div className="nr-name">{h.name}</div>
        <div className="nr-ip">{h.address}</div>
        <span className="nr-state">{isOn ? "в сети" : "не в сети"}</span>
      </button>
    );
  }

  const toggleOnline = () => {
    setUserTouched(true);
    setOpenOnline((v) => !v);
  };
  const toggleOffline = () => {
    setUserTouched(true);
    setOpenOffline((v) => !v);
  };

  return (
    <div className="nr-wrap">
      <style>{`
        .nr-wrap { display:flex; flex-direction:column; gap:6px; }

        /* Горизонтальные полосы-«вкладки»: плоские, на всю ширину, без закруглений. */
        .nr-row { display:flex; flex-direction:column; }
        .nr-row-head {
          width:100%; display:flex; align-items:center; gap:10px;
          padding:12px 2px; cursor:pointer; background:transparent; border:0;
          border-bottom:1px solid rgb(229 231 235); text-align:left; font-size:14px;
        }
        .dark .nr-row-head { border-bottom-color:#374151; }
        .nr-row-head:hover { background:rgba(0,0,0,.02); }
        .dark .nr-row-head:hover { background:rgba(255,255,255,.03); }
        .nr-row-dot { width:9px; height:9px; border-radius:50%; flex:none; }
        .nr-row-dot-on { background:#22c55e; }
        .nr-row-dot-off { background:#9ca3af; }
        .nr-row-title { font-weight:600; }
        .nr-row-count { font-size:11px; font-weight:700; padding:2px 9px; border-radius:20px; }
        .nr-row-count-on { background:rgba(34,197,94,.14); color:#16a34a; }
        .nr-row-count-off { background:rgba(156,163,175,.18); color:#6b7280; }
        .nr-row-chev { margin-left:auto; font-size:16px; color:#9ca3af; transition:transform .3s ease; }
        .nr-row-head.nr-head-open .nr-row-chev { transform:rotate(90deg); }

        .nr-row-body { display:grid; grid-template-rows:0fr; transition:grid-template-rows .4s ease; }
        .nr-row-head.nr-head-open ~ .nr-row-body { grid-template-rows:1fr; }
        .nr-row-inner { overflow:hidden; }

        .nr-grid { display:grid; gap:11px; padding:12px 0; grid-template-columns:1fr; }
        @media (min-width: 640px) { .nr-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } }
        @media (min-width: 1024px) { .nr-grid { grid-template-columns:repeat(3,minmax(0,1fr)); } }
        .nr-empty { font-size:13px; color:#9ca3af; padding:8px 0; }

        .nr-card { display:flex; align-items:center; gap:12px; text-align:left;
                   width:100%; padding:12px 14px; cursor:pointer;
                   border:1px solid rgb(229 231 235); border-radius:10px;
                   background:#fff;
                   transition: opacity 1s ease, background-color 1s ease, border-color 1s ease;
                   will-change: transform, opacity; }
        .dark .nr-card { background:#16181d; border-color:#374151; }
        .nr-card.nr-off { opacity:.5; }
        .nr-card.nr-off .nr-name { color:#6b7280; }
        .dark .nr-card.nr-off .nr-name { color:#9ca3af; }
        .nr-card.nr-sel { border-color:#2563eb; }
        .nr-card.nr-unsel { border-color:#d1d5db; }
        .dark .nr-card.nr-unsel { border-color:#4b5563; }
        .nr-dot { width:10px; height:10px; border-radius:50%; flex:none; }
        .nr-card.nr-on .nr-dot { background:#22c55e; }
        .nr-card.nr-off .nr-dot { background:#9ca3af; }
        .nr-name { min-width:0; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
        /* Моно-шрифт для адресов — как в прототипе. */
        .nr-ip { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
                 font-size:12.5px; color:#6b7280; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
        .dark .nr-ip { color:#9ca3af; }
        .nr-state { flex:none; font-size:10px; text-transform:uppercase; letter-spacing:.05em;
                    font-weight:700; padding:3px 8px; border-radius:20px; }
        .nr-card.nr-on .nr-state { background:rgba(34,197,94,.14); color:#16a34a; }
        .nr-card.nr-off .nr-state { background:rgba(156,163,175,.18); color:#6b7280; }
      `}</style>

      {/* Две горизонтальные полосы: заголовок + раскрывающийся контент, на всю ширину. */}
      <Row
        title="В сети"
        items={online}
        open={openOnline}
        toggle={toggleOnline}
        innerRef={onlineRef}
        tone="on"
        emptyText="Нет машин в сети"
        renderCard={renderCard}
      />
      <Row
        title="Не в сети"
        items={offline}
        open={openOffline}
        toggle={toggleOffline}
        innerRef={offlineRef}
        tone="off"
        emptyText="Все машины в сети"
        renderCard={renderCard}
      />
    </div>
  );
}
