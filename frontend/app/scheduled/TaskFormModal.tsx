"use client";

import { useMemo, useState } from "react";
import { Modal } from "@/components/Modal";
import { toLocalISO } from "@/lib/utils";
import type { ScheduledTask, Scenario, Host, Group } from "@/lib/schedule-types";
import {
  targetsFor, DAY_SHORT, toBitmask, hmToMinutes, durationToMinutes, minutesToHM, fromBitmask,
} from "@/lib/schedule-utils";

interface Props {
  title: string;
  task?: ScheduledTask | null; // при редактировании
  scenarios: Scenario[];
  hosts: Host[];
  groups: Group[];
  onClose: () => void;
  onSubmit: (data: Record<string, unknown>, isEdit: boolean) => void;
}

/** ISO (UTC+offset) -> локальное значение datetime-local "YYYY-MM-DDTHH:mm". */
function isoToLocalInput(iso?: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}

type Cond = "online" | "time";

export default function TaskFormModal({ title, task, scenarios, hosts, groups, onClose, onSubmit }: Props) {
  const isEdit = !!task;
  const isSchedule = useMemo(() => !!task && (task.days_of_week || "").includes("1"), [task]);

  const [name, setName] = useState(task?.name || "");
  const [description, setDescription] = useState(task?.description || "");
  const [scenarioId, setScenarioId] = useState<string>(task?.scenario_id ? String(task.scenario_id) : "");
  const [targetType, setTargetType] = useState<"host" | "group">(task?.target_type || "host");
  const [targetId, setTargetId] = useState<string>(task?.target_id ? String(task.target_id) : "");

  // Условие: «когда будет в сети» — по умолчанию (Сай).
  const [cond, setCond] = useState<Cond>(task ? (task.wait_for_online ? "online" : "time") : "online");
  const [once, setOnce] = useState<boolean>(!!task && !isSchedule && !task.wait_for_online);
  // Разовая по времени — конкретный момент
  const [runAt, setRunAt] = useState<string>(isoToLocalInput(task?.run_at));
  // Расписание (повтор): дни + окно + интервал
  const [days, setDays] = useState<number[]>(
    isSchedule ? fromBitmask(task?.days_of_week) : [],
  );
  const [startT, setStartT] = useState<string>(minutesToHM(task?.start_min));
  const [endT, setEndT] = useState<string>(minutesToHM(task?.end_min));
  const [intervalT, setIntervalT] = useState<string>(minutesToHM(task?.interval_min));

  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState(false);

  // Режим «по времени» виден всегда в этой форме; день/время — только при repeat.
  const showDays = cond === "time" && !once;
  const everyDay = days.length === 7;

  function toggleDay(i: number) {
    setDays((prev) => (prev.includes(i) ? prev.filter((x) => x !== i) : [...prev, i].sort((a, b) => a - b)));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    const base: Record<string, unknown> = {
      name: name.trim(),
      description: description.trim() || null,
      scenario_id: Number(scenarioId),
      target_type: targetType,
      target_id: Number(targetId),
    };

    if (!name.trim()) return setError("Введите название задачи");
    if (!scenarioId) return setError("Выберите сценарий");
    if (!targetId) return setError("Выберите цель");

    if (cond === "online") {
      // Разовая: выполнить, когда цель появится в сети.
      base.wait_for_online = true;
      base.days_of_week = "";
      base.run_at = toLocalISO(new Date());
    } else if (once) {
      // Разовая по времени: конкретный момент.
      if (!runAt) return setError("Укажите дату и время запуска");
      base.wait_for_online = false;
      base.days_of_week = "";
      base.run_at = toLocalISO(new Date(runAt));
    } else {
      // Расписание: дни + окно + интервал (run_at бэкенд вычислит сам).
      if (days.length === 0) return setError("Выберите хотя бы один день запуска");
      const startMin = hmToMinutes(startT);
      const endMin = hmToMinutes(endT);
      const intervalMin = durationToMinutes(intervalT);
      if (startMin === null) return setError("Укажите время «С»");
      if (endMin === null) return setError("Укажите время «До»");
      if (intervalMin === null) return setError("Укажите интервал «Каждые»");
      if (startMin >= endMin) return setError("Время «С» должно быть раньше «До»");
      if (intervalMin < 1) return setError("Интервал минимум 1 минута (ноль дал бы бесконечный цикл)");
      if (intervalMin > endMin - startMin) return setError("Интервал не должен быть длиннее окна запуска");
      base.days_of_week = toBitmask(days);
      base.start_min = startMin;
      base.end_min = endMin;
      base.interval_min = intervalMin;
      base.wait_for_online = false;
    }

    setLoading(true);
    try {
      await onSubmit(base, isEdit);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Modal title={title} onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid lg:grid-cols-[minmax(0,1fr)_16rem] gap-6">
          {/* Левая колонка */}
          <div className="space-y-4 min-w-0">
            <label className="label block">
              Название задачи
              <input className="input w-full" value={name} onChange={(e) => setName(e.target.value)} placeholder="Название задачи" />
            </label>
            <label className="label block">
              Описание задачи
              <textarea
                className="input w-full min-h-[90px] resize-y"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Описание задачи (необязательно)"
              />
            </label>

            {/* Режим «по времени» + повтор: день запуска и время запуска */}
            {cond === "time" && (
              <div className="space-y-4">
                {/* Запустить один раз */}
                <label className="flex items-center gap-3 cursor-pointer select-none w-fit">
                  <input type="checkbox" className="w-4 h-4" checked={once} onChange={(e) => setOnce(e.target.checked)} />
                  <span className="text-sm">Запустить один раз</span>
                </label>

                {once ? (
                  <label className="label block">
                    Время запуска
                    <input className="input w-full" type="datetime-local" value={runAt} onChange={(e) => setRunAt(e.target.value)} />
                  </label>
                ) : (
                  <>
                    {/* День запуска */}
                    <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4 space-y-3">
                      <div className="flex items-center justify-between gap-3">
                        <span className="font-semibold">День запуска</span>
                        <label className="inline-flex items-center gap-2 cursor-pointer text-sm select-none">
                          <input
                            type="checkbox"
                            className="w-4 h-4"
                            checked={everyDay}
                            onChange={(e) => setDays(e.target.checked ? [0, 1, 2, 3, 4, 5, 6] : [])}
                          />
                          Каждый день
                        </label>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {DAY_SHORT.map((d, i) => {
                          const active = days.includes(i);
                          return (
                            <button
                              key={i}
                              type="button"
                              onClick={() => toggleDay(i)}
                              className={`px-3 py-2 rounded-full text-sm border transition-colors ${
                                active
                                  ? "bg-blue-600 text-white border-blue-600"
                                  : "border-blue-600 text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-950/40"
                              }`}
                            >
                              {d}
                            </button>
                          );
                        })}
                      </div>
                    </div>

                    {/* Время запуска (окно + интервал) */}
                    <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4 space-y-3">
                      <span className="font-semibold">Время запуска</span>
                      <div className="flex flex-wrap items-center gap-x-5 gap-y-3">
                        <TimeRow label="С" value={startT} onChange={setStartT} />
                        <TimeRow label="Каждые" value={intervalT} onChange={setIntervalT} />
                        <TimeRow label="До" value={endT} onChange={setEndT} />
                      </div>
                      <p className="text-xs text-gray-500">
                        Срабатывает в окне с {startT || "С"} до {endT || "До"} с интервалом {intervalT || "—"}.
                      </p>
                    </div>
                  </>
                )}
              </div>
            )}

            {cond === "online" && (
              <p className="text-sm text-gray-500">
                Задача останется активной и выполнится сама, как только цель появится в сети.
              </p>
            )}
          </div>

          {/* Правая колонка */}
          <div className="space-y-4">
            <label className="label block">
              Тип цели
              <select
                className="input w-full"
                value={targetType}
                onChange={(e) => {
                  setTargetType(e.target.value as "host" | "group");
                  setTargetId("");
                }}
              >
                <option value="host">Хост</option>
                <option value="group">Группа</option>
              </select>
            </label>
            <label className="label block">
              Цель
              <select className="input w-full" value={targetId} onChange={(e) => setTargetId(e.target.value)}>
                <option value="">Выберите цель</option>
                {targetsFor(targetType, hosts, groups).map((x) => (
                  <option key={x.id} value={x.id}>
                    {x.name} #{x.id}
                  </option>
                ))}
              </select>
            </label>

            <fieldset className="space-y-1">
              <legend className="text-sm text-gray-500 mb-1">Сценарий</legend>
              <select className="input w-full" value={scenarioId} onChange={(e) => setScenarioId(e.target.value)}>
                <option value="">Выберите сценарий</option>
                {scenarios.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} #{s.id}
                  </option>
                ))}
              </select>
            </fieldset>

            <fieldset className="space-y-2 pt-2 border-t border-gray-200 dark:border-gray-700">
              <legend className="text-sm font-semibold text-gray-500">Условие запуска</legend>
              <label className="inline-flex items-center gap-2 text-sm cursor-pointer select-none">
                <input type="radio" checked={cond === "time"} onChange={() => setCond("time")} />
                По времени
              </label>
              <br />
              <label className="inline-flex items-center gap-2 text-sm cursor-pointer select-none">
                <input type="radio" checked={cond === "online"} onChange={() => setCond("online")} />
                Когда будет в сети
              </label>
            </fieldset>
          </div>
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <div className="flex gap-3 justify-end pt-2">
          <button type="button" className="btn-secondary" onClick={onClose}>
            Отмена
          </button>
          <button className="btn" type="submit" disabled={loading}>
            {isEdit ? "Сохранить" : "Создать"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

/** Подпись слева + <input type="time">. */
function TimeRow({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="inline-flex items-center gap-2 text-sm">
      <span className="text-gray-500">{label}</span>
      <input className="input" type="time" value={value} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}
