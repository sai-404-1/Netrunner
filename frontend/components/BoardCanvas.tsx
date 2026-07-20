"use client";

import { useRef, useState, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useTheme } from "@/components/ThemeProvider";
import { Monitor, X, ZoomIn, ZoomOut } from "lucide-react";

interface Host {
  id: number;
  name: string;
  address: string;
  is_active: boolean | number;
}

interface Placement {
  host_id: number;
  x: number;
  y: number;
  name: string;
  address: string;
  is_active: boolean | number;
}

interface Board {
  id: number;
  name: string;
  width: number;
  height: number;
}

interface Props {
  board: Board;
  availableHosts: Host[];
  initialPlacements: Placement[];
  onChange: (placements: Placement[]) => void;
}

const MIN_ZOOM = 0.1;
const MAX_ZOOM = 4;

/**
 * Доска — единая модель ввода на Pointer Events (не MouseEvent/HTML5 DnD): один
 * набор обработчиков одинаково работает мышью, пальцем и стилусом. Панорамирование
 * доски — обычный клик ЛКМ (или палец) по пустому месту, без модификаторов
 * (Space/средняя кнопка раньше требовались — убрано, т.к. не работает с тача и
 * недоступно для обнаружения на телефоне). Перетаскивание хоста на канве и с полки
 * снизу — тоже Pointer Events + setPointerCapture, чтобы жест не срывался, если
 * палец/курсор на миг выходит за границы элемента.
 */
export function BoardCanvas({ board, availableHosts, initialPlacements, onChange }: Props) {
  const router = useRouter();
  const { theme } = useTheme();
  const isDark = theme === "dark";
  const wrapRef = useRef<HTMLDivElement>(null);
  const [placements, setPlacements] = useState<Placement[]>(initialPlacements);
  const [zoom, setZoom] = useState(0.7);
  const [panX, setPanX] = useState(0);
  const [panY, setPanY] = useState(0);
  const [isPanning, setIsPanning] = useState(false);
  const panStartRef = useRef({ x: 0, y: 0, px: 0, py: 0 });
  const [dragging, setDragging] = useState<{ hostId: number; ox: number; oy: number } | null>(null);
  const activePointerRef = useRef<number | null>(null);
  // Активные пальцы на фоне канвы (макс. 2 — для щипка) и состояние щипка между move-событиями.
  const pointersRef = useRef<Map<number, { x: number; y: number }>>(new Map());
  const pinchRef = useRef<{ lastDist: number } | null>(null);
  // Перетаскивание хоста с полки снизу на канву — "призрак" следует за пальцем/курсором.
  const [shelfDrag, setShelfDrag] = useState<{ hostId: number; x: number; y: number } | null>(null);
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<"name" | "status">("name");

  useEffect(() => {
    setPlacements(initialPlacements);
  }, [initialPlacements]);

  useEffect(() => {
    onChange(placements);
  }, [placements, onChange]);

  const placedIds = new Set(placements.map((p) => p.host_id));

  const panelHosts = availableHosts
    .filter((h) => {
      if (placedIds.has(h.id)) return false;
      if (search && !h.name.toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    })
    .sort((a, b) => {
      if (sortBy === "status") return Number(b.is_active) - Number(a.is_active);
      return a.name.localeCompare(b.name);
    });

  const zoomAt = useCallback((factor: number, clientX?: number, clientY?: number) => {
    const rect = wrapRef.current?.getBoundingClientRect();
    const mx = clientX != null && rect ? clientX - rect.left : (rect?.width ?? 0) / 2;
    const my = clientY != null && rect ? clientY - rect.top : (rect?.height ?? 0) / 2;
    setZoom((z) => {
      const nz = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, z * factor));
      setPanX((px) => mx / nz - mx / z + px);
      setPanY((py) => my / nz - my / z + py);
      return nz;
    });
  }, []);

  // React навешивает onWheel как passive-листенер, поэтому e.preventDefault() внутри
  // синтетического обработчика браузер молча игнорирует — скролл всё равно уходит на
  // страницу, та упирается в край и делает эластичный bounce (мелькает белый фон
  // платформы). Вешаем нативный listener с passive:false, чтобы preventDefault реально
  // сработал и страница вокруг доски не скроллилась вовсе.
  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const onWheelNative = (e: WheelEvent) => {
      e.preventDefault();
      // Экспоненциальный шаг, пропорциональный deltaY — мягче фиксированных ±10%
      // за тик и остаётся плавным как на мышином колесе, так и на трекпаде.
      zoomAt(Math.exp(-e.deltaY * 0.0005), e.clientX, e.clientY);
    };
    el.addEventListener("wheel", onWheelNative, { passive: false });
    return () => el.removeEventListener("wheel", onWheelNative);
  }, [zoomAt]);

  // --- Панорамирование доски (клик/палец по пустому фону канвы) --------------
  const startPan = useCallback(
    (e: React.PointerEvent) => {
      // Только основной контакт: ЛКМ (button 0), средняя кнопка (1) как алтернатива
      // для привычки — правый клик (контекстное меню) не трогаем.
      if (e.pointerType === "mouse" && e.button !== 0 && e.button !== 1) return;
      e.preventDefault();
      // Третий и далее палец игнорируем полностью — щипок работает строго на первых двух.
      if (pointersRef.current.size >= 2) return;
      (e.currentTarget as Element).setPointerCapture(e.pointerId);
      pointersRef.current.set(e.pointerId, { x: e.clientX, y: e.clientY });

      if (pointersRef.current.size === 2) {
        // Второй палец лёг на канву — переходим в режим щипка, одиночное
        // панорамирование первым пальцем отменяем.
        activePointerRef.current = null;
        setIsPanning(false);
        const pts = Array.from(pointersRef.current.values());
        pinchRef.current = { lastDist: Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y) };
        return;
      }

      activePointerRef.current = e.pointerId;
      setIsPanning(true);
      panStartRef.current = { x: e.clientX, y: e.clientY, px: panX, py: panY };
    },
    [panX, panY]
  );

  const onCanvasPointerMove = useCallback(
    (e: React.PointerEvent) => {
      if (pointersRef.current.has(e.pointerId)) {
        pointersRef.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
      }

      if (pinchRef.current && pointersRef.current.size === 2) {
        const pts = Array.from(pointersRef.current.values());
        const dist = Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y);
        const mx = (pts[0].x + pts[1].x) / 2;
        const my = (pts[0].y + pts[1].y) / 2;
        if (pinchRef.current.lastDist > 0 && dist > 0) {
          zoomAt(dist / pinchRef.current.lastDist, mx, my);
        }
        pinchRef.current.lastDist = dist;
        return;
      }

      if (e.pointerId !== activePointerRef.current) return;
      if (isPanning) {
        const dx = (e.clientX - panStartRef.current.x) / zoom;
        const dy = (e.clientY - panStartRef.current.y) / zoom;
        setPanX(panStartRef.current.px + dx);
        setPanY(panStartRef.current.py + dy);
      } else if (dragging) {
        const rect = wrapRef.current!.getBoundingClientRect();
        const x = (e.clientX - rect.left) / zoom - panX + dragging.ox;
        const y = (e.clientY - rect.top) / zoom - panY + dragging.oy;
        setPlacements((prev) =>
          prev.map((p) => (p.host_id === dragging.hostId ? { ...p, x, y } : p))
        );
      }
    },
    [isPanning, zoom, panX, panY, dragging, zoomAt]
  );

  const endInteraction = useCallback((e: React.PointerEvent) => {
    pointersRef.current.delete(e.pointerId);
    if (pointersRef.current.size < 2) pinchRef.current = null;
    if (e.pointerId !== activePointerRef.current) return;
    activePointerRef.current = null;
    setIsPanning(false);
    setDragging(null);
  }, []);

  // --- Перетаскивание уже размещённого хоста по канве -------------------------
  const startDragHost = useCallback(
    (hostId: number, e: React.PointerEvent) => {
      e.preventDefault();
      e.stopPropagation();
      (e.currentTarget as Element).setPointerCapture(e.pointerId);
      activePointerRef.current = e.pointerId;
      const rect = wrapRef.current!.getBoundingClientRect();
      const placement = placements.find((p) => p.host_id === hostId)!;
      const hx = placement.x + panX;
      const hy = placement.y + panY;
      const mx = (e.clientX - rect.left) / zoom;
      const my = (e.clientY - rect.top) / zoom;
      setDragging({ hostId, ox: hx - mx, oy: hy - my });
    },
    [placements, panX, panY, zoom]
  );

  const removePlacement = useCallback((hostId: number) => {
    setPlacements((prev) => prev.filter((p) => p.host_id !== hostId));
  }, []);

  // --- Перетаскивание хоста с полки снизу на канву (без HTML5 DnD — тач не тянет) ---
  const startShelfDrag = useCallback((hostId: number, e: React.PointerEvent) => {
    e.preventDefault();
    (e.currentTarget as Element).setPointerCapture(e.pointerId);
    activePointerRef.current = e.pointerId;
    setShelfDrag({ hostId, x: e.clientX, y: e.clientY });
  }, []);

  const onShelfPointerMove = useCallback((e: React.PointerEvent) => {
    if (e.pointerId !== activePointerRef.current || !shelfDrag) return;
    setShelfDrag({ ...shelfDrag, x: e.clientX, y: e.clientY });
  }, [shelfDrag]);

  const endShelfDrag = useCallback(
    (e: React.PointerEvent) => {
      if (e.pointerId !== activePointerRef.current) return;
      activePointerRef.current = null;
      if (shelfDrag) {
        const rect = wrapRef.current?.getBoundingClientRect();
        if (rect && e.clientX >= rect.left && e.clientX <= rect.right && e.clientY >= rect.top && e.clientY <= rect.bottom) {
          const host = availableHosts.find((h) => h.id === shelfDrag.hostId);
          if (host) {
            const x = (e.clientX - rect.left) / zoom - panX;
            const y = (e.clientY - rect.top) / zoom - panY;
            setPlacements((prev) => {
              const exists = prev.find((p) => p.host_id === host.id);
              if (exists) return prev.map((p) => (p.host_id === host.id ? { ...p, x, y } : p));
              return [...prev, { host_id: host.id, x, y, name: host.name, address: host.address, is_active: host.is_active }];
            });
          }
        }
      }
      setShelfDrag(null);
    },
    [shelfDrag, availableHosts, zoom, panX, panY]
  );

  const cursor = isPanning ? "grabbing" : dragging ? "move" : "grab";

  return (
    <div className="flex flex-col h-full select-none">
      <div
        ref={wrapRef}
        className="flex-1 relative overflow-hidden bg-gray-50 border rounded-xl"
        style={{ cursor, minHeight: 0, touchAction: "none" }}
        onPointerDown={startPan}
        onPointerMove={onCanvasPointerMove}
        onPointerUp={endInteraction}
        onPointerCancel={endInteraction}
      >
        <div
          style={{
            width: board.width,
            height: board.height,
            transform: `scale(${zoom}) translate(${panX}px, ${panY}px)`,
            transformOrigin: "0 0",
            position: "relative",
            background: isDark ? "#0f172a" : "white",
            boxShadow: isDark ? "0 0 0 1px #334155" : "0 0 0 1px #e2e8f0",
            backgroundImage: isDark
              ? "radial-gradient(circle, #334155 1px, transparent 1px)"
              : "radial-gradient(circle, #d1d5db 1px, transparent 1px)",
            backgroundSize: "24px 24px",
          }}
        >
          {placements.map((p) => (
            <div
              key={p.host_id}
              style={{
                position: "absolute",
                left: p.x - 32,
                top: p.y - 44,
                width: 64,
                cursor: "move",
                userSelect: "none",
                touchAction: "none",
              }}
              onPointerDown={(e) => startDragHost(p.host_id, e)}
              onDoubleClick={(e) => { e.stopPropagation(); router.push(`/run?host=${p.host_id}`); }}
            >
              <div className="flex flex-col items-center gap-0.5">
                <button
                  className="absolute -top-2 -right-2 w-5 h-5 rounded-full bg-red-500 text-white flex items-center justify-center text-xs leading-none z-10"
                  onPointerDown={(e) => e.stopPropagation()}
                  onClick={() => removePlacement(p.host_id)}
                >
                  <X size={10} />
                </button>
                <Monitor
                  size={36}
                  className={p.is_active ? "text-green-500" : "text-gray-400"}
                />
                <span
                  className="text-xs text-center w-full truncate text-gray-700 font-medium"
                  style={{ maxWidth: 64 }}
                >
                  {p.name}
                </span>
              </div>
            </div>
          ))}
        </div>

        {/* Кнопки +/- зума — на телефоне нет колеса мыши для zoomAt-по-wheel */}
        <div className="absolute bottom-3 right-3 flex flex-col gap-1 z-20">
          <button
            type="button"
            className="btn-secondary p-2 shadow"
            onPointerDown={(e) => e.stopPropagation()}
            onClick={() => zoomAt(1.25)}
            title="Приблизить"
          >
            <ZoomIn size={16} />
          </button>
          <button
            type="button"
            className="btn-secondary p-2 shadow"
            onPointerDown={(e) => e.stopPropagation()}
            onClick={() => zoomAt(0.8)}
            title="Отдалить"
          >
            <ZoomOut size={16} />
          </button>
        </div>
      </div>

      <div className="h-28 border-t flex items-stretch gap-3 p-2 bg-white shrink-0">
        {/* Левая колонка: поиск и сортировка */}
        <div className="flex flex-col justify-center gap-2 w-40 shrink-0">
          <input
            className="input text-sm py-1"
            placeholder="Поиск..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <select
            className="input text-sm py-1"
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as "name" | "status")}
          >
            <option value="name">По имени</option>
            <option value="status">По статусу</option>
          </select>
        </div>
        {/* Справа: список компьютеров — тянем на канву пальцем или мышью */}
        <div className="flex gap-2 overflow-x-auto items-center flex-1">
          {panelHosts.map((h) => (
            <div
              key={h.id}
              onPointerDown={(e) => startShelfDrag(h.id, e)}
              onPointerMove={onShelfPointerMove}
              onPointerUp={endShelfDrag}
              onPointerCancel={endShelfDrag}
              style={{ touchAction: "none" }}
              className="flex flex-col items-center w-16 shrink-0 cursor-grab py-1 px-1 rounded-lg hover:bg-gray-100 border border-transparent hover:border-gray-200"
              title={h.address}
            >
              <Monitor size={28} className={h.is_active ? "text-green-500" : "text-gray-400"} />
              <span className="text-xs truncate w-full text-center text-gray-700 mt-0.5">
                {h.name}
              </span>
            </div>
          ))}
          {panelHosts.length === 0 && (
            <span className="text-xs text-gray-400 self-center px-2">
              {availableHosts.length === placedIds.size ? "Все хосты размещены" : "Нет совпадений"}
            </span>
          )}
        </div>
      </div>

      {/* Призрак перетаскиваемого с полки хоста — следует за пальцем/курсором */}
      {shelfDrag && (() => {
        const host = availableHosts.find((h) => h.id === shelfDrag.hostId);
        if (!host) return null;
        return (
          <div
            className="fixed pointer-events-none z-50 flex flex-col items-center opacity-80"
            style={{ left: shelfDrag.x - 28, top: shelfDrag.y - 28, width: 56 }}
          >
            <Monitor size={32} className={host.is_active ? "text-green-500" : "text-gray-400"} />
            <span className="text-xs text-center w-full truncate text-gray-700 font-medium bg-white/80 rounded px-1">
              {host.name}
            </span>
          </div>
        );
      })()}
    </div>
  );
}
