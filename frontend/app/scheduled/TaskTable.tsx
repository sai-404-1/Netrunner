"use client";

import type { ScheduledTask, Scenario, Host, Group } from "@/lib/schedule-types";
import { taskScenarioIds, taskTargetIds } from "@/lib/schedule-types";
import { scheduleLabel } from "@/lib/schedule-utils";
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
          render: (t) => {
            const ids = taskScenarioIds(t);
            if (ids.length === 0) return "—";
            const names = ids.map((id) => scenarios.find((x) => x.id === id)?.name || `#${id}`);
            return (
              <span className="text-sm">
                {names.length > 2 ? `${ids.length} сценария(ев)` : names.join(", ")}
              </span>
            );
          },
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
            const [hostIds, groupIds] = taskTargetIds(t);
            const parts: string[] = [];
            if (hostIds.length) {
              parts.push(
                "хост: " +
                  hostIds
                    .map((id) => hosts.find((h) => h.id === id)?.name || `#${id}`)
                    .join(", "),
              );
            }
            if (groupIds.length) {
              parts.push(
                "группа: " +
                  groupIds
                    .map((id) => groups.find((g) => g.id === id)?.name || `#${id}`)
                    .join(", "),
              );
            }
            if (parts.length === 0) parts.push("—");
            const full = parts.join(" · ");
            return (
              <span className="text-sm" title={full}>
                {full.length > 40 ? full.slice(0, 40) + "…" : full}
              </span>
            );
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
