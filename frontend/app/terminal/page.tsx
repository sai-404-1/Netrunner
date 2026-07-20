"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import "@xterm/xterm/css/xterm.css";
import { useAuth } from "@/components/AuthProvider";
import { apiGetClient } from "@/lib/api-client";

export default function TerminalPage() {
  return (
    <Suspense fallback={<div className="p-6">Загрузка...</div>}>
      <TerminalView />
    </Suspense>
  );
}

interface Host {
  id: number;
  name: string;
  address: string;
}

/** WebTerminal — интерактивный shell к хосту через ssh -tt + локальный PTY на
 * бэкенде (webui/terminal_handler.py), только суперпользователь. */
function TerminalView() {
  const { user } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const hostId = params.get("host") || "";

  const [host, setHost] = useState<Host | null>(null);
  const [status, setStatus] = useState<"connecting" | "connected" | "closed">("connecting");
  const containerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<Terminal | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (user && !user.is_superuser) router.replace("/");
  }, [user, router]);

  useEffect(() => {
    if (!hostId) return;
    apiGetClient(`/api/hosts`)
      .then((hosts: Host[]) => setHost((hosts || []).find((h) => h.id === Number(hostId)) || null))
      .catch(() => {});
  }, [hostId]);

  useEffect(() => {
    if (!hostId || !containerRef.current) return;

    const term = new Terminal({
      cursorBlink: true,
      fontSize: 13,
      theme: { background: "#0f172a" },
    });
    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    term.open(containerRef.current);
    fitAddon.fit();
    termRef.current = term;

    const wsUrl = `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}/api/python/api/terminal/ws?host_id=${hostId}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

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

    const onData = term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "input", data }));
    });

    const onResize = () => {
      fitAddon.fit();
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "resize", cols: term.cols, rows: term.rows }));
      }
    };
    window.addEventListener("resize", onResize);

    return () => {
      window.removeEventListener("resize", onResize);
      onData.dispose();
      ws.close();
      term.dispose();
      termRef.current = null;
      wsRef.current = null;
    };
  }, [hostId]);

  if (!hostId) {
    return <div className="p-6">Не указан хост (<code>?host=&lt;id&gt;</code>).</div>;
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-3xl font-bold">Терминал</h2>
        <p className="text-gray-500">
          {host ? `${host.name} (${host.address})` : `Хост #${hostId}`} —{" "}
          {status === "connecting" && "подключение…"}
          {status === "connected" && <span className="text-green-500">подключено</span>}
          {status === "closed" && <span className="text-red-500">соединение закрыто</span>}
        </p>
      </div>
      <div className="panel p-2">
        <div ref={containerRef} style={{ height: "calc(100vh - 260px)" }} />
      </div>
    </div>
  );
}
