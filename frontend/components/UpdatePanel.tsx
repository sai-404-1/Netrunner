"use client";

import { useEffect, useState } from "react";
import { apiGetClient, apiPostClient } from "@/lib/api-client";
import { useToast } from "@/components/Toast";
import { RefreshCw, Download, GitBranch, Save, History } from "lucide-react";

interface UpdateConfig {
  remote: string;
  branch: string;
  has_token: boolean;
  auto_update: boolean;
  poll_interval: number;
}

interface UpdateStatus {
  git?: boolean;
  branch?: string;
  behind?: number;
  up_to_date?: boolean;
  last_remote?: string;
  diff_stats?: string;
  error?: string;
  checked_at?: string;
}

interface Incident {
  name: string;
  content: string;
}

/** Раздел «Обновление» — git-монитор: настройка, статус, применение, инциденты. */
export function UpdatePanel() {
  const showToast = useToast();
  const [config, setConfig] = useState<UpdateConfig | null>(null);
  const [status, setStatus] = useState<UpdateStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [applying, setApplying] = useState(false);

  const [remote, setRemote] = useState("");
  const [branch, setBranch] = useState("");
  const [token, setToken] = useState("");
  const [pollInterval, setPollInterval] = useState("600");

  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [showIncidents, setShowIncidents] = useState(false);

  async function loadStatus() {
    try {
      const data = await apiGetClient("/api/update/status");
      setConfig(data.config);
      setStatus(data.status);
      setRemote(data.config?.remote || "");
      setBranch(data.config?.branch || "");
      setPollInterval(String(data.config?.poll_interval || 600));
    } catch (e: any) {
      showToast(e.message, "error");
    }
  }

  useEffect(() => {
    loadStatus();
  }, []);

  async function saveConfig(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const body: any = { remote, branch, poll_interval: Number(pollInterval) };
      if (token) body.token = token; // пусто — не менять
      const cfg = await apiPostClient("/api/update/config", body);
      setConfig(cfg);
      setToken("");
      showToast("Настройки сохранены");
    } catch (e: any) {
      showToast(e.message, "error");
    } finally {
      setSaving(false);
    }
  }

  async function recheck() {
    setLoading(true);
    try {
      const r = await apiPostClient("/api/update/recheck", {});
      setStatus(r);
      if (r.error) showToast(r.error, "error");
    } catch (e: any) {
      showToast(e.message, "error");
    } finally {
      setLoading(false);
    }
  }

  function waitForRestart() {
    let tries = 0;
    const t = setInterval(async () => {
      tries++;
      try {
        const res = await fetch("/api/python/healthz");
        if (res.ok) {
          clearInterval(t);
          showToast("Сервер снова доступен");
          setApplying(false);
          loadStatus();
        }
      } catch {
        /* ещё перезапускается */
      }
      if (tries > 200) {
        clearInterval(t);
        setApplying(false);
      }
    }, 3000);
  }

  async function apply() {
    if (!confirm("Применить обновление? Сервер перезапустится и пересоберёт фронт — это может занять несколько минут.")) return;
    setApplying(true);
    try {
      const r = await apiPostClient("/api/update/apply", {});
      if (r.ok) {
        showToast("Обновление применяется. Ожидаю перезапуск сервера…");
        waitForRestart();
      } else {
        showToast(r.error || "Не удалось применить обновление", "error");
        setApplying(false);
      }
    } catch (e: any) {
      showToast(e.message, "error");
      setApplying(false);
    }
  }

  async function toggleIncidents() {
    const next = !showIncidents;
    setShowIncidents(next);
    if (next && incidents.length === 0) {
      try {
        const d = await apiGetClient("/api/update/incidents");
        setIncidents(d.incidents || []);
      } catch (e: any) {
        showToast(e.message, "error");
      }
    }
  }

  const behind = status?.behind ?? 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <GitBranch size={18} className="text-gray-400" />
        <h3 className="font-semibold">Обновление</h3>
      </div>

      {/* Настройка репозитория */}
      <form onSubmit={saveConfig} className="space-y-3">
        <label className="label">
          Git-репозиторий
          <input className="input" value={remote} onChange={(e) => setRemote(e.target.value)} placeholder="https://github.com/org/netrunner.git" />
        </label>
        <div className="grid grid-cols-2 gap-3">
          <label className="label">
            Ветка
            <input className="input" value={branch} onChange={(e) => setBranch(e.target.value)} placeholder="main" />
          </label>
          <label className="label">
            Интервал, сек
            <input className="input" type="number" min={60} value={pollInterval} onChange={(e) => setPollInterval(e.target.value)} />
          </label>
        </div>
        <label className="label">
          Deploy-токен {config?.has_token && <span className="text-xs text-green-500">(сохранён)</span>}
          <input
            className="input"
            type="password"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder={config?.has_token ? "•••••• (оставьте пустым, чтобы не менять)" : "read-only PAT / deploy token"}
          />
        </label>
        <button className="btn-secondary" type="submit" disabled={saving}>
          <Save size={16} /> {saving ? "Сохранение…" : "Сохранить настройки"}
        </button>
      </form>

      {/* Статус и действия */}
      <div className="pt-3 border-t border-gray-200 dark:border-gray-700 space-y-3">
        <div className="flex gap-3 flex-wrap">
          <button onClick={recheck} disabled={loading || applying} className="btn-secondary">
            <RefreshCw size={16} className={loading ? "animate-spin" : ""} /> Проверить сейчас
          </button>
          {behind > 0 && (
            <button onClick={apply} disabled={applying} className="btn">
              <Download size={16} className={applying ? "animate-spin" : ""} /> {applying ? "Применяется…" : `Применить (${behind})`}
            </button>
          )}
        </div>

        {status?.error && <p className="text-sm text-red-500">❌ {status.error}</p>}
        {status && !status.error && status.git && (
          <div className="text-sm space-y-1">
            {status.up_to_date ? (
              <p className="text-green-500">✅ Актуальная версия (ветка {status.branch})</p>
            ) : (
              <p className="text-orange-500">
                📦 Доступно обновление: отставание на <strong>{behind}</strong> коммит(ов)
              </p>
            )}
            {status.last_remote && <p className="text-gray-500">Удалённый HEAD: {status.last_remote}</p>}
            {status.checked_at && <p className="text-xs text-gray-500">Проверено: {new Date(status.checked_at).toLocaleString()}</p>}
            {status.diff_stats && (
              <pre className="bg-slate-950 text-gray-200 p-3 rounded text-xs whitespace-pre-wrap max-h-40 overflow-auto">{status.diff_stats}</pre>
            )}
          </div>
        )}
        {status && !status.git && (
          <p className="text-sm text-gray-500">
            Самообновление недоступно: проект развёрнут без git-репозитория (нужен bind-mount деплой).
          </p>
        )}
      </div>

      {/* Инциденты супервизора */}
      <div className="pt-3 border-t border-gray-200 dark:border-gray-700">
        <button onClick={toggleIncidents} className="btn-secondary text-sm">
          <History size={15} /> {showIncidents ? "Скрыть историю" : "История инцидентов"}
        </button>
        {showIncidents && (
          <div className="mt-3 space-y-2">
            {incidents.length === 0 && <p className="text-sm text-gray-500">Инцидентов нет</p>}
            {incidents.map((i) => (
              <details key={i.name} className="text-xs">
                <summary className="cursor-pointer text-blue-500">{i.name}</summary>
                <pre className="bg-slate-950 text-gray-200 p-3 rounded whitespace-pre-wrap max-h-48 overflow-auto mt-1">{i.content}</pre>
              </details>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
