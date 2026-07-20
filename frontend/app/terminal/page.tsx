"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import { apiGetClient } from "@/lib/api-client";
import { useTerminalManager, confirmDisconnect } from "@/components/TerminalManagerProvider";

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
 * бэкенде (webui/terminal_handler.py), только суперпользователь.
 *
 * Само WS-соединение и xterm-инстанс живут в TerminalManagerProvider (в
 * Layout, не перемонтируется при переходах между страницами) — эта страница
 * только подключает/отключает свой DOM-контейнер к уже существующему (или
 * новому) соединению. Уход со страницы НЕ закрывает соединение — оно
 * продолжает жить в фоне и видно в сайдбаре, пока не нажать «Отключиться». */
function TerminalView() {
  const { user } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const hostId = params.get("host") || "";
  const manager = useTerminalManager();
  // Деструктурируем стабильные функции отдельно от manager: сам объект
  // manager пересоздаётся при КАЖДОМ изменении connMetas (в том числе при
  // отключении), а get/getOrCreate — стабильные ссылки (useCallback с []).
  // Если положить в deps эффекта весь manager, отключение тут же перезапустит
  // эффект и getOrCreate молча создаст соединение заново поверх disconnect.
  const { get, getOrCreate } = manager;

  const [host, setHost] = useState<Host | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

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
    const id = Number(hostId);
    const existing = get(id);
    // Для уже открытого в фоне соединения имя/адрес не нужны — переиспользуем
    // как есть. Для нового соединения ждём загрузки данных хоста (нужны
    // имя/адрес и для строки в сайдбаре, и для отображения в шапке).
    if (!existing && !host) return;
    const conn = getOrCreate(id, host?.name || existing!.hostName, host?.address || existing!.hostAddress);

    const el = containerRef.current;
    el.appendChild(conn.container);
    conn.fitAddon.fit();
    if (conn.ws.readyState === WebSocket.OPEN) {
      conn.ws.send(JSON.stringify({ type: "resize", cols: conn.term.cols, rows: conn.term.rows }));
    }

    const onResize = () => {
      conn.fitAddon.fit();
      if (conn.ws.readyState === WebSocket.OPEN) {
        conn.ws.send(JSON.stringify({ type: "resize", cols: conn.term.cols, rows: conn.term.rows }));
      }
    };
    window.addEventListener("resize", onResize);

    return () => {
      window.removeEventListener("resize", onResize);
      // НЕ закрываем соединение — просто отсоединяем DOM-контейнер от текущей
      // страницы, он продолжает жить в фоне (в TerminalManagerProvider).
      if (conn.container.parentElement === el) {
        el.removeChild(conn.container);
      }
    };
  }, [hostId, host, get, getOrCreate]);

  if (!hostId) {
    return <div className="p-6">Не указан хост (<code>?host=&lt;id&gt;</code>).</div>;
  }

  const id = Number(hostId);
  const meta = manager.connMetas.find((m) => m.hostId === id);
  const status = meta?.status;
  const displayName = host ? `${host.name} (${host.address})` : meta ? `${meta.hostName} (${meta.hostAddress})` : `Хост #${hostId}`;

  function handleDisconnect() {
    if (!confirmDisconnect(host?.name || meta?.hostName || `#${hostId}`)) return;
    manager.disconnect(id);
    router.push("/hosts");
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-3xl font-bold">Терминал</h2>
        <p className="text-gray-500">
          {displayName} —{" "}
          {!status && "не подключено"}
          {status === "connecting" && "подключение…"}
          {status === "connected" && <span className="text-green-500">подключено</span>}
          {status === "closed" && <span className="text-red-500">соединение закрыто</span>}
        </p>
      </div>
      <div className="panel p-2">
        <div ref={containerRef} style={{ height: "calc(100vh - 320px)" }} />
      </div>
      {meta && (
        <button className="btn-danger" onClick={handleDisconnect}>
          Отключиться
        </button>
      )}
    </div>
  );
}
