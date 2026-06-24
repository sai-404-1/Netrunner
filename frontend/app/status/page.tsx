"use client";

import { useEffect, useState } from "react";
import { AlertCircle, RefreshCw, Server } from "lucide-react";

type ServerState = "checking" | "online" | "offline" | "restarting" | "maintenance";

function probe(): Promise<ServerState> {
  return fetch("/api/python/api/summary", { credentials: "include", cache: "no-store" })
    .then((r) => {
      if (r.ok || r.status === 401) return "online" as ServerState;
      if (r.status === 503) return "maintenance" as ServerState;
      return "offline" as ServerState;
    })
    .catch(() => "offline" as ServerState);
}

const STATE_LABELS: Record<ServerState, { title: string; desc: string; color: string }> = {
  checking: {
    title: "Проверка соединения...",
    desc: "Опрашиваем сервер NetRunner.",
    color: "text-gray-500",
  },
  online: {
    title: "Сервер работает",
    desc: "Всё в порядке. Можете перейти на главную.",
    color: "text-green-600",
  },
  offline: {
    title: "Сервер недоступен",
    desc: "Сервер не отвечает. Возможно, он перезагружается или требует ручного вмешательства.",
    color: "text-red-600",
  },
  restarting: {
    title: "Сервер перезагружается",
    desc: "Подождите — сервер скоро будет доступен.",
    color: "text-amber-600",
  },
  maintenance: {
    title: "Техническое обслуживание",
    desc: "Сервер временно недоступен: резервное копирование или плановые работы.",
    color: "text-blue-600",
  },
};

export default function StatusPage() {
  const [state, setState] = useState<ServerState>("checking");
  const [lastChecked, setLastChecked] = useState<Date | null>(null);
  const [checking, setChecking] = useState(false);
  const [wasOffline, setWasOffline] = useState(false);

  async function check(autoRedirect = false) {
    setChecking(true);
    setState("checking");
    const s = await probe();
    setState(s);
    setLastChecked(new Date());
    setChecking(false);
    if (s !== "online" && s !== "checking") {
      setWasOffline(true);
    }
    if (s === "online" && wasOffline && autoRedirect) {
      setTimeout(() => {
        window.location.href = "/";
      }, 1500);
    }
  }

  useEffect(() => {
    check(false);
    const interval = setInterval(() => check(true), 15000);
    return () => clearInterval(interval);
  }, [wasOffline]);

  const info = STATE_LABELS[state];

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <div className="panel w-full max-w-md text-center space-y-6">
        <div className="flex justify-center">
          {state === "online" ? (
            <div className="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center">
              <Server size={32} className="text-green-600" />
            </div>
          ) : state === "checking" ? (
            <div className="w-16 h-16 rounded-full bg-gray-100 flex items-center justify-center">
              <RefreshCw size={32} className="text-gray-400 animate-spin" />
            </div>
          ) : (
            <div className="w-16 h-16 rounded-full bg-red-100 flex items-center justify-center">
              <AlertCircle size={32} className={info.color} />
            </div>
          )}
        </div>

        <div>
          <h1 className={`text-2xl font-bold ${info.color}`}>{info.title}</h1>
          <p className="text-gray-500 mt-2 text-sm">{info.desc}</p>
        </div>

        {lastChecked && (
          <p className="text-xs text-gray-400">
            Последняя проверка: {lastChecked.toLocaleTimeString("ru-RU")}
          </p>
        )}

        <div className="flex flex-col gap-3">
          <button className="btn w-full" onClick={() => check(false)} disabled={checking}>
            <RefreshCw size={16} className={checking ? "animate-spin" : ""} />
            Проверить снова
          </button>
          <a href="/" className="btn-secondary w-full justify-center">
            На главную
          </a>
        </div>

        <div className="text-xs text-gray-400 border-t pt-4 text-left space-y-1">
          <p className="font-semibold text-gray-500">Статусы:</p>
          <p>🟢 <strong>Работает</strong> — сервер отвечает нормально</p>
          <p>🔴 <strong>Недоступен</strong> — не отвечает, нужна проверка</p>
          <p>🟡 <strong>Перезагрузка</strong> — временно недоступен, скоро вернётся</p>
          <p>🔵 <strong>Обслуживание</strong> — плановые работы</p>
        </div>
      </div>
    </div>
  );
}
