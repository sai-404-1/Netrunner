"use client";

import { useRef, useState, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Monitor, X } from "lucide-react";

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

export function BoardCanvas({ board, availableHosts, initialPlacements, onChange }: Props) {
  const router = useRouter();
  const wrapRef = useRef<HTMLDivElement>(null);
  const [placements, setPlacements] = useState<Placement[]>(initialPlacements);
  const [zoom, setZoom] = useState(0.7);
  const [panX, setPanX] = useState(0);
  const [panY, setPanY] = useState(0);
  const [isPanning, setIsPanning] = useState(false);
  const [panStart, setPanStart] = useState({ x: 0, y: 0, px: 0, py: 0 });
  const [spaceDown, setSpaceDown] = useState(false);
  const [dragging, setDragging] = useState<{ hostId: number; ox: number; oy: number } | null>(null);
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

  const handleWheel = useCallback(
    (e: React.WheelEvent) => {
      e.preventDefault();
      const factor = e.deltaY < 0 ? 1.1 : 0.9;
      const rect = wrapRef.current!.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      setZoom((z) => {
        const nz = Math.min(4, Math.max(0.1, z * factor));
        setPanX((px) => mx / nz - mx / z + px);
        setPanY((py) => my / nz - my / z + py);
        return nz;
      });
    },
    []
  );

  const startPan = useCallback(
    (e: React.MouseEvent) => {
      if (!spaceDown && e.button !== 1) return;
      e.preventDefault();
      setIsPanning(true);
      setPanStart({ x: e.clientX, y: e.clientY, px: panX, py: panY });
    },
    [spaceDown, panX, panY]
  );

  const onMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (isPanning) {
        const dx = (e.clientX - panStart.x) / zoom;
        const dy = (e.clientY - panStart.y) / zoom;
        setPanX(panStart.px + dx);
        setPanY(panStart.py + dy);
      } else if (dragging) {
        const rect = wrapRef.current!.getBoundingClientRect();
        const x = (e.clientX - rect.left) / zoom - panX + dragging.ox;
        const y = (e.clientY - rect.top) / zoom - panY + dragging.oy;
        setPlacements((prev) =>
          prev.map((p) => (p.host_id === dragging.hostId ? { ...p, x, y } : p))
        );
      }
    },
    [isPanning, panStart, zoom, panX, panY, dragging]
  );

  const endDrag = useCallback(() => {
    setIsPanning(false);
    setDragging(null);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const hostId = Number(e.dataTransfer.getData("host_id"));
      if (!hostId) return;
      const host = availableHosts.find((h) => h.id === hostId);
      if (!host) return;
      const rect = wrapRef.current!.getBoundingClientRect();
      const x = (e.clientX - rect.left) / zoom - panX;
      const y = (e.clientY - rect.top) / zoom - panY;
      setPlacements((prev) => {
        const exists = prev.find((p) => p.host_id === hostId);
        if (exists) return prev.map((p) => (p.host_id === hostId ? { ...p, x, y } : p));
        return [...prev, { host_id: hostId, x, y, name: host.name, address: host.address, is_active: host.is_active }];
      });
    },
    [availableHosts, zoom, panX, panY]
  );

  const startDragHost = useCallback(
    (hostId: number, e: React.MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
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

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.code === "Space" && e.target === document.body) {
        e.preventDefault();
        setSpaceDown(true);
      }
    };
    const onKeyUp = (e: KeyboardEvent) => {
      if (e.code === "Space") setSpaceDown(false);
    };
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
    };
  }, []);

  const cursor = spaceDown ? (isPanning ? "grabbing" : "grab") : dragging ? "move" : "default";

  return (
    <div className="flex flex-col h-full select-none">
      <div
        ref={wrapRef}
        className="flex-1 relative overflow-hidden bg-gray-50 border rounded-xl"
        style={{ cursor, minHeight: 0 }}
        onWheel={handleWheel}
        onMouseDown={startPan}
        onMouseMove={onMouseMove}
        onMouseUp={endDrag}
        onMouseLeave={endDrag}
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
      >
        <div
          style={{
            width: board.width,
            height: board.height,
            transform: `scale(${zoom}) translate(${panX}px, ${panY}px)`,
            transformOrigin: "0 0",
            position: "relative",
            background: "white",
            boxShadow: "0 0 0 1px #e2e8f0",
            backgroundImage:
              "radial-gradient(circle, #d1d5db 1px, transparent 1px)",
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
              }}
              onMouseDown={(e) => startDragHost(p.host_id, e)}
              onDoubleClick={(e) => { e.stopPropagation(); router.push(`/run?host=${p.host_id}`); }}
            >
              <div className="flex flex-col items-center gap-0.5">
                <button
                  className="absolute -top-2 -right-2 w-4 h-4 rounded-full bg-red-500 text-white flex items-center justify-center text-xs leading-none z-10"
                  onMouseDown={(e) => e.stopPropagation()}
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
      </div>

      <div className="h-28 border-t flex items-center gap-2 p-2 overflow-x-auto bg-white shrink-0">
        <input
          className="input w-36 shrink-0 text-sm py-1"
          placeholder="Поиск..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          className="input w-32 shrink-0 text-sm py-1"
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as "name" | "status")}
        >
          <option value="name">По имени</option>
          <option value="status">По статусу</option>
        </select>
        <div className="flex gap-2 overflow-x-auto">
          {panelHosts.map((h) => (
            <div
              key={h.id}
              draggable
              onDragStart={(e) => e.dataTransfer.setData("host_id", String(h.id))}
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
    </div>
  );
}
