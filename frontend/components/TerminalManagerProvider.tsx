"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import "@xterm/xterm/css/xterm.css";

export interface TerminalConnection {
  hostId: number;
  hostName: string;
  hostAddress: string;
  ws: WebSocket;
  term: Terminal;
  fitAddon: FitAddon;
  container: HTMLDivElement;
}

export interface TerminalConnMeta {
  hostId: number;
  hostName: string;
  hostAddress: string;
  status: "connecting" | "connected" | "closed";
}

interface TerminalManagerValue {
  connMetas: TerminalConnMeta[];
  get: (hostId: number) => TerminalConnection | undefined;
  getOrCreate: (hostId: number, hostName: string, hostAddress: string) => TerminalConnection;
  disconnect: (hostId: number) => void;
}

const TerminalManagerContext = createContext<TerminalManagerValue | null>(null);

export function useTerminalManager(): TerminalManagerValue {
  const ctx = useContext(TerminalManagerContext);
  if (!ctx) throw new Error("useTerminalManager должен использоваться внутри TerminalManagerProvider");
  return ctx;
}

export function confirmDisconnect(hostLabel: string): boolean {
  return window.confirm(`Отключиться от «${hostLabel}»? Соединение с терминалом будет закрыто.`);
}

/** Единая точка правды для WS-подключений к консолям хостов (WebTerminal).
 * Провайдер смонтирован в Layout, который не перемонтируется при переходах
 * между страницами (см. комментарий про LAST_TAB_KEY в Layout.tsx) — поэтому
 * сами WebSocket+xterm-инстансы переживают переключение вкладок: страница
 * /terminal только подключает свой DOM-контейнер к уже существующему
 * соединению (или создаёт новое), а при уходе со страницы просто отсоединяет
 * контейнер от видимой области, не трогая ни WebSocket, ни сам xterm — вывод
 * продолжает копиться в буфере терминала в фоне. */
export function TerminalManagerProvider({ children }: { children: React.ReactNode }) {
  const connectionsRef = useRef<Map<number, TerminalConnection>>(new Map());
  const [connMetas, setConnMetas] = useState<TerminalConnMeta[]>([]);

  const get = useCallback((hostId: number) => connectionsRef.current.get(hostId), []);

  const getOrCreate = useCallback((hostId: number, hostName: string, hostAddress: string) => {
    const existing = connectionsRef.current.get(hostId);
    if (existing) return existing;

    const container = document.createElement("div");
    container.style.width = "100%";
    container.style.height = "100%";

    const term = new Terminal({ cursorBlink: true, fontSize: 13, theme: { background: "#0f172a" } });
    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    term.open(container);

    const wsUrl = `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}/api/python/api/terminal/ws?host_id=${hostId}`;
    const ws = new WebSocket(wsUrl);

    const conn: TerminalConnection = { hostId, hostName, hostAddress, ws, term, fitAddon, container };
    connectionsRef.current.set(hostId, conn);
    // Новые подключения — в конец списка (появляются снизу в сайдбаре, старые
    // визуально "поднимаются" вверх по мере роста списка).
    setConnMetas((prev) => [...prev, { hostId, hostName, hostAddress, status: "connecting" }]);

    const setStatus = (status: TerminalConnMeta["status"]) => {
      setConnMetas((prev) => prev.map((m) => (m.hostId === hostId ? { ...m, status } : m)));
    };

    ws.onopen = () => {
      setStatus("connected");
      fitAddon.fit();
      ws.send(JSON.stringify({ type: "resize", cols: term.cols, rows: term.rows }));
    };
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "output") term.write(data.data);
      } catch {}
    };
    ws.onclose = () => setStatus("closed");
    ws.onerror = () => setStatus("closed");

    term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "input", data }));
    });

    return conn;
  }, []);

  const disconnect = useCallback((hostId: number) => {
    const conn = connectionsRef.current.get(hostId);
    if (!conn) return;
    try {
      conn.ws.close();
    } catch {}
    try {
      conn.term.dispose();
    } catch {}
    connectionsRef.current.delete(hostId);
    setConnMetas((prev) => prev.filter((m) => m.hostId !== hostId));
  }, []);

  // Предупреждение при закрытии САМОЙ ВКЛАДКИ браузера (не при переходах
  // внутри приложения — client-side навигация beforeunload не вызывает),
  // пока есть хоть одно активное соединение. Текст диалога браузер формирует
  // сам — это ограничение всех современных браузеров с ~2016 года, кастомный
  // текст в beforeunload они больше не показывают из соображений защиты от
  // спама, поэтому e.returnValue тут только включает сам факт предупреждения.
  useEffect(() => {
    function handler(e: BeforeUnloadEvent) {
      if (connectionsRef.current.size > 0) {
        e.preventDefault();
        e.returnValue = "";
      }
    }
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, []);

  const value = useMemo<TerminalManagerValue>(
    () => ({ connMetas, get, getOrCreate, disconnect }),
    [connMetas, get, getOrCreate, disconnect]
  );

  return <TerminalManagerContext.Provider value={value}>{children}</TerminalManagerContext.Provider>;
}
