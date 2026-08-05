"use client";

import { useState } from "react";
import { Modal } from "@/components/Modal";
import type { Template, Host, Group } from "@/lib/schedule-types";
import { targetsFor } from "@/lib/schedule-utils";

interface Props {
  templates: Template[];
  hosts: Host[];
  groups: Group[];
  onClose: () => void;
  onCreate: (fd: FormData) => void;
}

export default function CreateTaskModal({ templates, hosts, groups, onClose, onCreate }: Props) {
  const [targetType, setTargetType] = useState<"host" | "group">("host");

  return (
    <Modal title="Создание задачи" onClose={onClose}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onCreate(new FormData(e.currentTarget));
        }}
        className="flex flex-wrap gap-4 items-end"
      >
        <label className="label flex-1 min-w-[200px]">
          Название
          <input className="input" name="name" placeholder="Плановая инвентаризация" required />
        </label>
        <label className="label flex-1 min-w-[200px]">
          Шаблон
          <select className="input" name="template_id" required>
            {templates.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name} #{t.id}
              </option>
            ))}
          </select>
        </label>
        <label className="label flex-1 min-w-[140px]">
          Тип цели
          <select
            className="input"
            name="target_type"
            value={targetType}
            onChange={(e) => setTargetType(e.target.value as "host" | "group")}
          >
            <option value="host">Хост</option>
            <option value="group">Группа</option>
          </select>
        </label>
        <label className="label flex-1 min-w-[200px]">
          Цель
          <select className="input" name="target_id" required>
            {targetsFor(targetType, hosts, groups).map((x) => (
              <option key={x.id} value={x.id}>
                {x.name} #{x.id}
              </option>
            ))}
          </select>
        </label>
        <label className="label flex-1 min-w-[200px]">
          Время запуска
          <input className="input" name="run_at" type="datetime-local" required />
        </label>
        <button className="btn" type="submit">
          Создать
        </button>
      </form>
    </Modal>
  );
}