"use client";

import { useState } from "react";
import { Modal } from "@/components/Modal";
import type { Scenario, Host, Group } from "@/lib/schedule-types";
import { targetsFor } from "@/lib/schedule-utils";

interface Props {
  scenarios: Scenario[];
  hosts: Host[];
  groups: Group[];
  onClose: () => void;
  onCreate: (fd: FormData) => void;
}

/** Текущее локальное время в формате datetime-local (для online-задач: run_at
 * бэкенду нужен, но не важен, пока стоит wait_for_online). */
function localNow(): string {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}

export default function CreateTaskModal({ scenarios, hosts, groups, onClose, onCreate }: Props) {
  const [targetType, setTargetType] = useState<"host" | "group">("host");
  const [trigger, setTrigger] = useState<"time" | "online">("time");

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    if (trigger === "online") {
      // run_at колонка NOT NULL; при ожидании сети она не важна, ставим «сейчас».
      fd.set("run_at", localNow());
      fd.set("wait_for_online", "1");
    } else {
      fd.delete("wait_for_online");
    }
    onCreate(fd);
  }

  return (
    <Modal title="Создание задачи" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <label className="label block">
          Название
          <input className="input w-full" name="name" placeholder="Плановая инвентаризация" required />
        </label>
        <label className="label block">
          Сценарий
          <select className="input w-full" name="scenario_id" required>
            <option value="">Выберите сценарий</option>
            {scenarios.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} #{s.id}
                {s.step_count ? ` (${s.step_count} шаг.)` : ""}
              </option>
            ))}
          </select>
        </label>

        <fieldset className="label">
          <span>Условие запуска</span>
          <div className="flex gap-5 mt-1">
            <label className="inline-flex items-center gap-2 text-sm cursor-pointer">
              <input type="radio" name="trigger" checked={trigger === "time"} onChange={() => setTrigger("time")} />
              По времени
            </label>
            <label className="inline-flex items-center gap-2 text-sm cursor-pointer">
              <input type="radio" name="trigger" checked={trigger === "online"} onChange={() => setTrigger("online")} />
              Когда хост появится в сети
            </label>
          </div>
        </fieldset>

        {trigger === "time" ? (
          <label className="label block">
            Время запуска
            <input className="input w-full" name="run_at" type="datetime-local" required />
          </label>
        ) : (
          <p className="text-sm text-gray-500">
            Задача останется активной и выполнится сама, как только цель появится в сети.
          </p>
        )}

        <div className="grid grid-cols-2 gap-4">
          <label className="label block">
            Тип цели
            <select
              className="input w-full"
              name="target_type"
              value={targetType}
              onChange={(e) => setTargetType(e.target.value as "host" | "group")}
            >
              <option value="host">Хост</option>
              <option value="group">Группа</option>
            </select>
          </label>
          <label className="label block">
            Цель
            <select className="input w-full" name="target_id" required>
              <option value="">Выберите цель</option>
              {targetsFor(targetType, hosts, groups).map((x) => (
                <option key={x.id} value={x.id}>
                  {x.name} #{x.id}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="flex gap-3 justify-end">
          <button type="button" className="btn-secondary" onClick={onClose}>
            Отмена
          </button>
          <button className="btn" type="submit">
            Создать
          </button>
        </div>
      </form>
    </Modal>
  );
}
