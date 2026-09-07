"use client";

import type { ScheduledTask, Scenario, Host, Group } from "@/lib/schedule-types";
import { targetsFor, scheduleLabel } from "@/lib/schedule-utils";
import { DataTable } from "@/components/DataTable";
import { Pencil, Trash2 } from "lucide-react";

interface Props {
  rows: ScheduledTask[];
  scenarios: Scenario[];
  hosts: Host[];
  groups: Group[];
  onEdit: (task: ScheduledTask) => void;
  onDelete: (id: number) => void;
  onToggle: (task: ScheduledTask) => void;
}

export default function TaskTable({ rows, scenarios, hosts, groups, onEdit, onDelete, onToggle }: Props) {
  return (
    <DataTable
      columns={[
        {
          title: "Название",
          render: (t) => <span title={t.description || undefined}>{t.name}</span>,
        },
        {
          title: "Сценарий",
          render: (t) => scenarios.find((x) => x.id === t.scenario_id)?.name || `#${t.scenario_id}`,
        },
        {
          title: "Условие",
          render: (t) => (
            <span className="text-sm">{scheduleLabel(t)}</span>
          ),
        },
        {
          title: "Цель",
          render: (t) => {
            const target = targetsFor(t.target_type, hosts, groups).find((x) => x.id === t.target_id);
            return `${t.target_type === "host" ? "хост" : "группа"}:${target?.name || t.target_id}`;
          },
        },
        {
          title: "Активна",
          render: (t) => (
            <input
              type="checkbox"
              className="w-4 h-4"
              checked={!!t.is_enabled}
              onChange={() => onToggle(t)}
              title={t.is_enabled ? "Отключить" : "Активировать"}
            />
          ),
        },
        {
          title: "",
          render: (t) => (
            <div className="flex gap-2 justify-end">
              <button className="btn-secondary p-2" onClick={() => onEdit(t)} title="Редактировать">
                <Pencil size={16} />
              </button>
              <button className="btn-secondary p-2 text-red-600" onClick={() => onDelete(t.id)} title="Удалить">
                <Trash2 size={16} />
              </button>
            </div>
          ),
        },
      ]}
      rows={rows}
    />
  );
}
