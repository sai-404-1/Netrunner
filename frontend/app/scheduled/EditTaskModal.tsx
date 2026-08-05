"use client";

import type { ScheduledTask, Template, Host, Group } from "@/lib/schedule-types";
import { targetsFor } from "@/lib/schedule-utils";
import { Modal } from "@/components/Modal";

interface Props {
  task: ScheduledTask;
  templates: Template[];
  hosts: Host[];
  groups: Group[];
  onClose: () => void;
  onSubmit: (fd: FormData) => void;
}

export default function EditTaskModal({ task, templates, hosts, groups, onClose, onSubmit }: Props) {

  return (
    <Modal title="Редактирование задачи" onClose={onClose}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit(new FormData(e.currentTarget));
        }}
        className="grid gap-4"
      >
        <input type="hidden" name="id" value={task.id} />
        <label className="label">
          Название
          <input className="input" name="name" defaultValue={task.name} required />
        </label>
        <label className="label">
          Шаблон
          <select className="input" name="template_id" defaultValue={task.template_id}>
            {templates.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name} #{t.id}
              </option>
            ))}
          </select>
        </label>
        <label className="label">
          Тип цели
          <select className="input" name="target_type" defaultValue={task.target_type}>
            <option value="host">Хост</option>
            <option value="group">Группа</option>
          </select>
        </label>
        <label className="label">
          Цель
          <select className="input" name="target_id" defaultValue={task.target_id}>
            {targetsFor(task.target_type, hosts, groups).map((x) => (
              <option key={x.id} value={x.id}>
                {x.name} #{x.id}
              </option>
            ))}
          </select>
        </label>
        <label className="label">
          Время запуска
          <input className="input" name="run_at" type="datetime-local" defaultValue={task.run_at ? task.run_at.slice(0, 16) : ""} required />
        </label>
        <label className="label inline-flex flex-row items-center gap-3 cursor-pointer">
          <input type="checkbox" name="is_enabled" defaultChecked={task.is_enabled} className="w-5 h-5" />
          <span>Активна</span>
        </label>
        <div className="flex gap-3">
          <button className="btn" type="submit">
            Сохранить
          </button>
          <button type="button" className="btn-secondary" onClick={onClose}>
            Отмена
          </button>
        </div>
      </form>
    </Modal>
  )
}