"use client";

import { useCallback, useEffect, useState } from "react";
import { apiGetClient } from "@/lib/api-client";
import { formatDate } from "@/lib/utils";
import { StatusBadge } from "@/components/Badge";
import { DataTable } from "@/components/DataTable";
import Link from "next/link";
import { ArrowRight, Server, Users, Layers, FileText, Activity, AlertCircle, CheckCircle, XCircle } from "lucide-react";

interface GroupStat {
  id: number;
  name: string;
  kind: string;
  total: number;
  online: number;
  offline: number;
}

interface Summary {
  hosts: number;
  hosts_online: number;
  groups: number;
  modules: number;
  task_runs: number;
  scheduled: number;
  reports: number;
  group_stats: GroupStat[];
  recent_task_runs: any[];
  latest_inventory: any[];
  latest_reports: any[];
}

export default function DashboardPage() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [hosts, setHosts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const [s, h] = await Promise.all([
        apiGetClient("/api/summary"),
        apiGetClient("/api/hosts"),
      ]);
      setSummary(s);
      setHosts(h || []);
    } catch {} finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    // Auto-refresh every 15 seconds
    const interval = setInterval(load, 15000);
    return () => clearInterval(interval);
  }, [load]);

  if (loading) return <div className="p-6 text-gray-500">Загрузка...</div>;

  const online = summary?.hosts_online ?? 0;
  const total = summary?.hosts ?? 0;
  const offline = total - online;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold">Обзор</h2>
        <p className="text-gray-500">Сводная панель состояния системы</p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <SummaryCard title="Онлайн" value={online} icon={<Activity size={20} />} color="text-green-600" />
        <SummaryCard title="Всего хостов" value={total} icon={<Server size={20} />} color="text-blue-600" />
        <SummaryCard title="Модули" value={summary?.modules ?? 0} icon={<Layers size={20} />} color="text-purple-600" />
        <SummaryCard title="Группы" value={summary?.groups ?? 0} icon={<Users size={20} />} color="text-amber-600" />
      </div>

      {/* Second row */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <SummaryCard title="Запущено задач" value={summary?.task_runs ?? 0} icon={<Activity size={20} />} color="text-cyan-600" />
        <SummaryCard title="Отчётов" value={summary?.reports ?? 0} icon={<FileText size={20} />} color="text-indigo-600" />
        <SummaryCard title="Недоступно" value={offline} icon={<XCircle size={20} />} color="text-red-600" />
      </div>

      {/* Group widgets */}
      {summary?.group_stats && summary.group_stats.length > 0 && (
        <div className="panel">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold">Статус по группам</h3>
            <Link href="/hosts" className="btn-secondary py-1.5 px-3 text-sm">
              <ArrowRight size={14} /> Все хосты
            </Link>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {summary.group_stats.map((g) => (
              <Link
                key={g.id}
                href={`/hosts?group=${g.id}`}
                className="border border-gray-200 rounded-xl p-4 hover:bg-gray-50 transition-colors block"
              >
                <div className="flex items-center justify-between mb-3">
                  <span className="font-semibold text-sm">{g.name}</span>
                  <span className="text-xs text-gray-500">{g.kind === "custom" ? "пользовательская" : g.kind}</span>
                </div>
                <div className="flex items-center gap-4 text-sm">
                  <div className="flex items-center gap-1.5">
                    <CheckCircle size={14} className="text-green-600" />
                    <span className="font-medium text-green-700">{g.online}</span>
                    <span className="text-gray-500">в сети</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <XCircle size={14} className="text-red-500" />
                    <span className="font-medium text-red-600">{g.offline}</span>
                    <span className="text-gray-500">нет</span>
                  </div>
                </div>
                <div className="mt-3 w-full bg-gray-200 rounded-full h-1.5 overflow-hidden">
                  <div
                    className="bg-green-600 h-full rounded-full transition-all"
                    style={{ width: `${g.total > 0 ? (g.online / g.total) * 100 : 0}%` }}
                  />
                </div>
                <div className="mt-1 text-xs text-gray-400 text-right">{g.total} хостов</div>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Recent activity */}
      <div className="grid lg:grid-cols-2 gap-6">
        <div className="panel">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold">Последние задачи</h3>
            <Link href="/history" className="btn-secondary py-1.5 px-3 text-sm">
              <ArrowRight size={14} /> История
            </Link>
          </div>
          <RecentActivity runs={summary?.recent_task_runs || []} />
        </div>

        <div className="panel">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold">Статус хостов</h3>
            <Link href="/hosts" className="btn-secondary py-1.5 px-3 text-sm">
              <ArrowRight size={14} /> Подробнее
            </Link>
          </div>
          <HostStatusSummary hosts={hosts} />
        </div>
      </div>

      {/* Errors widget */}
      {summary?.recent_task_runs && summary.recent_task_runs.filter((r: any) => r.status === "error").length > 0 && (
        <div className="panel border-red-200">
          <h3 className="font-semibold mb-4 flex items-center gap-2">
            <AlertCircle size={18} className="text-red-600" />
            Последние ошибки
          </h3>
          <RecentErrors runs={summary.recent_task_runs.filter((r: any) => r.status === "error")} />
        </div>
      )}
    </div>
  );
}

function SummaryCard({ title, value, icon, color }: { title: string; value: number; icon: React.ReactNode; color: string }) {
  return (
    <div className="card">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-gray-500 uppercase tracking-wide">{title}</span>
        <span className={color}>{icon}</span>
      </div>
      <strong className="block text-3xl font-bold">{value}</strong>
    </div>
  );
}

function HostStatusSummary({ hosts }: { hosts: any[] }) {
  if (!hosts.length) return <p className="text-gray-500">Нет зарегистрированных хостов</p>;
  const active = hosts.filter((h) => h.is_active).length;
  const inactive = hosts.length - active;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-4 text-sm">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-green-600" />
          <strong>{active}</strong> активных
        </div>
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-red-600" />
          <strong>{inactive}</strong> недоступных
        </div>
      </div>
      <DataTable
        columns={[
          { title: "Хост", key: "name" },
          { title: "Адрес", render: (h) => `${h.username}@${h.address}:${h.port}` },
          { title: "Статус", render: (h) => (h.is_active ? <span className="badge badge-success">Активен</span> : <span className="badge badge-error">Недоступен</span>) },
        ]}
        rows={hosts.slice(0, 10)}
      />
    </div>
  );
}

function RecentActivity({ runs }: { runs: any[] }) {
  if (!runs.length) return <p className="text-gray-500">Нет задач</p>;
  return (
    <div className="space-y-2">
      {runs.slice(0, 8).map((run) => {
        const icon = run.status === "success" ? <CheckCircle size={14} className="text-green-600" /> :
                     run.status === "error" ? <XCircle size={14} className="text-red-600" /> :
                     <Activity size={14} className="text-amber-600" />;
        const moduleName = run.module_id ? `#${run.module_id}` : "—";
        return (
          <div key={run.id} className="flex items-center justify-between p-2 border border-gray-100 rounded-lg text-sm">
            <div className="flex items-center gap-2">
              {icon}
              <span className="font-medium">Задача #{run.id}</span>
              <span className="text-gray-500">модуль {moduleName}</span>
              <span className="text-gray-400 text-xs">{run.target_type}:{run.target_id}</span>
            </div>
            <span className="text-xs text-gray-400">{run.started_at ? formatDate(run.started_at) : "—"}</span>
          </div>
        );
      })}
    </div>
  );
}

function RecentErrors({ runs }: { runs: any[] }) {
  return (
    <div className="space-y-2">
      {runs.slice(0, 5).map((run) => (
        <div key={run.id} className="p-3 bg-red-50 border border-red-200 rounded-xl text-sm">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-medium">Задача #{run.id}</span>
            <span className="text-gray-500 text-xs">{formatDate(run.started_at)}</span>
          </div>
          <pre className="text-red-700 text-xs mt-1 overflow-hidden max-h-16">
            {(run.stdout_text || run.stderr_text || "—").substring(0, 300)}
          </pre>
        </div>
      ))}
    </div>
  );
}
