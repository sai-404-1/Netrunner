import { apiGet } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { StatusBadge } from "@/components/Badge";
import { DataTable } from "@/components/DataTable";
import Link from "next/link";
import { ArrowRight } from "lucide-react";

export default async function DashboardPage() {
  const summary: any = await apiGet("/api/summary");
  const hosts: any[] = await apiGet("/api/hosts");
  const online = (hosts || []).filter((h) => h.is_active).length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold">Обзор</h2>
          <p className="text-gray-500">Сводная панель состояния системы</p>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <SummaryCard title="Онлайн" value={online} />
        <SummaryCard title="Модули" value={summary.modules} />
        <SummaryCard title="Группы" value={summary.groups} />
        <SummaryCard title="Отчёты" value={summary.reports} />
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        <div className="panel">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold">Статус хостов</h3>
            <Link href="/hosts" className="btn-secondary py-1.5 px-3 text-sm">
              Подробнее <ArrowRight size={14} />
            </Link>
          </div>
          <HostStatusSummary hosts={hosts || []} />
        </div>

        <div className="panel">
          <h3 className="font-semibold mb-4">Последние задачи</h3>
          <RecentRunsTable runs={summary.recent_task_runs || []} />
        </div>
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        <div className="panel">
          <h3 className="font-semibold mb-4">Последняя инвентаризация</h3>
          <DataTable
            columns={[
              { title: "Host ID", key: "host_id" },
              { title: "Hostname", key: "hostname" },
              { title: "OS", key: "os_name" },
              { title: "Дата", render: (r: any) => formatDate(r.collected_at) },
            ]}
            rows={summary.latest_inventory || []}
            emptyText="Нет данных"
          />
        </div>

        <div className="panel">
          <h3 className="font-semibold mb-4">Последние отчёты</h3>
          <DataTable
            columns={[
              { title: "Название", key: "name" },
              { title: "Тип", key: "report_type" },
              { title: "Формат", key: "format" },
              { title: "Дата", render: (r: any) => formatDate(r.created_at) },
            ]}
            rows={summary.latest_reports || []}
            emptyText="Нет отчётов"
          />
        </div>
      </div>
    </div>
  );
}

function SummaryCard({ title, value }: { title: string; value: number }) {
  return (
    <div className="card">
      <span className="text-xs text-gray-500 uppercase tracking-wide">{title}</span>
      <strong className="block text-3xl font-bold mt-2">{value}</strong>
    </div>
  );
}

function HostStatusSummary({ hosts }: { hosts: any[] }) {
  if (!hosts.length) {
    return <p className="text-gray-500">Нет зарегистрированных хостов</p>;
  }
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
        rows={hosts}
      />
    </div>
  );
}

function RecentRunsTable({ runs }: { runs: any[] }) {
  return (
    <DataTable
      columns={[
        { title: "ID", key: "id" },
        { title: "Цель", render: (r) => `${r.target_type}:${r.target_id}` },
        { title: "Статус", render: (r) => <StatusBadge status={r.status} /> },
        { title: "Запуск", render: (r) => formatDate(r.started_at || r.created_at) },
      ]}
      rows={runs}
      emptyText="Нет задач"
    />
  );
}
