"use client";

import type { ScheduledTask, Scenario, Host, Group } from "@/lib/schedule-types";
import { targetsFor } from "@/lib/schedule-utils";
import { formatDate } from "@/lib/utils";
import { DataTable } from "@/components/DataTable";
import { Pencil, Trash2 } from "lucide-react";

interface Props {
  rows: ScheduledTask[];
  scenarios: Scenario[];
  hosts: Host[];
  groups: Group[];
  onEdit: (task: ScheduledTask) => void;
  onDelete: (id: number) => void;
}

export default function TaskTable({ rows, scenarios, hosts, groups, onEdit, onDelete }: Props) {
  return (
    <DataTable
      columns={[
        { title: "Название", key: "name" },
        {
          title: "Сценарий",
          render: (t) => scenarios.find((x) => x.id === t.scenario_id)?.name || `#${t.scenario_id}`,
        },
        {
          title: "Условие",
          render: (t) =>
            t.wait_for_online ? (
              <span className="inline-flex items-center gap-1.5 text-amber-600 dark:text-amber-400">
                по появлению в сети
              </span>
            ) : (
              formatDate(t.run_at)
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
