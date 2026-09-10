"use client";

import { useMemo, useState } from "react";
import { Modal } from "@/components/Modal";
import { toLocalISO } from "@/lib/utils";
import type { ScheduledTask, Scenario, Host, Group } from "@/lib/schedule-types";
import { taskScenarioIds, taskTargetIds } from "@/lib/schedule-types";
import {
  DAY_SHORT, toBitmask, hmToMinutes, durationToMinutes, minutesToHM, fromBitmask,
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

  // Мульти-выбор сценариев
  const [scenarioIds, setScenarioIds] = useState<number[]>(
    task ? taskScenarioIds(task) : [],
  );
  // Мульти-выбор цели: отдельно хосты и отдельно группы
  const [targetHostIds, setTargetHostIds] = useState<number[]>(
    task ? taskTargetIds(task)[0] : [],
  );
  const [targetGroupIds, setTargetGroupIds] = useState<number[]>(
    task ? taskTargetIds(task)[1] : [],
  );
  const [targetTab, setTargetTab] = useState<"host" | "group">("host");

  const [name, setName] = useState(task?.name || "");
  const [description, setDescription] = useState(task?.description || "");

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

  // Хосты онлайн сверху (для фильтра «сверху вниз»).
  const sortedHosts = useMemo(() => {
    return [...hosts].sort((a, b) => {
      const ao = a.is_active ? 1 : 0;
      const bo = b.is_active ? 1 : 0;
      if (ao !== bo) return bo - ao;
      return a.name.localeCompare(b.name);
    });
  }, [hosts]);

  function toggleId(list: number[], setList: (v: number[]) => void, id: number) {
    setList(list.includes(id) ? list.filter((x) => x !== id) : [...list, id]);
  }

  function toggleScenario(id: number) {
    toggleId(scenarioIds, setScenarioIds, id);
  }

  function toggleHost(id: number) {
    toggleId(targetHostIds, setTargetHostIds, id);
  }

  function toggleGroup(id: number) {
    toggleId(targetGroupIds, setTargetGroupIds, id);
  }

  function toggleDay(i: number) {
    setDays((prev) => (prev.includes(i) ? prev.filter((x) => x !== i) : [...prev, i].sort((a, b) => a - b)));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    const base: Record<string, unknown> = {
      name: name.trim(),
      description: description.trim() || null,
      scenario_id: scenarioIds[0] || null,
      target_type: "host",
      target_id: targetHostIds[0] || targetGroupIds[0] || 0,
      // Мульти-выбор: отправляем массивы (бэкенд сериализует в JSON).
      scenario_ids: scenarioIds,
      target_host_ids: targetHostIds,
      target_group_ids: targetGroupIds,
    };

    if (!name.trim()) return setError("Введите название задачи");
    if (scenarioIds.length === 0) return setError("Выберите хотя бы один сценарий");
    if (targetHostIds.length === 0 && targetGroupIds.length === 0)
      return setError("Выберите цель: хотя бы один хост или группу");

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
    <Modal title={title} onClose={onClose} size="lg">
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
                              className={`btn-secondary px-3 py-2 font-medium ${
                                active
                                  ? "border-blue-600 bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300"
                                  : ""
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
            {/* Цель — мульти-выбор: вкладки Хосты/Группы, можно выбрать несколько. */}
            <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4 space-y-3">
              <div className="flex items-center justify-between gap-3">
                <span className="font-semibold">Цель</span>
                <span className="text-xs text-gray-500">
                  {targetHostIds.length + targetGroupIds.length} выбрано
                </span>
              </div>

              {/* Вкладки: Хосты / Группы */}
              <div className="flex gap-1 border-b border-gray-200 dark:border-gray-700">
                {(["host", "group"] as const).map((tab) => (
                  <button
                    key={tab}
                    type="button"
                    onClick={() => setTargetTab(tab)}
                    className={`px-3 py-1.5 text-sm font-semibold border-b-2 -mb-px transition-colors ${
                      targetTab === tab
                        ? "border-blue-600 text-blue-600"
                        : "border-transparent text-gray-500 hover:text-gray-700"
                    }`}
                  >
                    {tab === "host" ? "Хосты" : "Группы"}
                  </button>
                ))}
              </div>

              {/* Список выбора — чипы, онлайн-хосты сверху */}
              <div className="max-h-56 overflow-y-auto space-y-2">
                {targetTab === "host" ? (
                  sortedHosts.length === 0 ? (
                    <p className="text-sm text-gray-500">Хостов нет</p>
                  ) : (
                    sortedHosts.map((h) => {
                      const on = targetHostIds.includes(h.id);
                      return (
                        <button
                          key={h.id}
                          type="button"
                          onClick={() => toggleHost(h.id)}
                          className={`btn w-full justify-between px-3 py-2 text-sm font-medium ${
                            on
                              ? "border-blue-600 bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300"
                              : "btn-secondary"
                          }`}
                        >
                          <span className="flex items-center gap-2">
                            <span
                              className={`inline-block w-2 h-2 rounded-full ${h.is_active ? "bg-green-500" : "bg-gray-400"}`}
                            />
                            {h.name} #{h.id}
                          </span>
                          <span className="text-xs">
                            {h.is_active ? "онлайн" : "офлайн"}
                          </span>
                        </button>
                      );
                    })
                  )
                ) : groups.length === 0 ? (
                  <p className="text-sm text-gray-500">Групп нет</p>
                ) : (
                  groups.map((g) => {
                    const on = targetGroupIds.includes(g.id);
                    return (
                      <button
                        key={g.id}
                        type="button"
                        onClick={() => toggleGroup(g.id)}
                        className={`btn w-full flex items-center justify-between px-3 py-2 text-sm font-medium ${
                          on
                            ? "border-blue-600 bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300"
                            : "btn-secondary"
                        }`}
                      >
                        <span>{g.name} #{g.id}</span>
                        {on && <span className="text-xs">✓</span>}
                      </button>
                    );
                  })
                )}
              </div>
            </div>

            {/* Сценарии — мульти-выбор чекбоксами */}
            <fieldset className="space-y-2">
              <legend className="text-sm font-semibold text-gray-500">
                Сценарии ({scenarioIds.length} выбрано)
              </legend>
              {scenarios.length === 0 ? (
                <p className="text-sm text-gray-500">Сценариев нет</p>
              ) : (
                <div className="space-y-1 max-h-40 overflow-y-auto">
                  {scenarios.map((s) => {
                    const on = scenarioIds.includes(s.id);
                    return (
                      <label
                        key={s.id}
                        className="flex items-center gap-2 text-sm cursor-pointer select-none px-2 py-1.5 rounded hover:bg-slate-50 dark:hover:bg-gray-700/50"
                      >
                        <input
                          type="checkbox"
                          className="w-4 h-4"
                          checked={on}
                          onChange={() => toggleScenario(s.id)}
                        />
                        <span className="flex-1">
                          {s.name} #{s.id}
                        </span>
                        {on && <span className="text-blue-600 text-xs">✓</span>}
                      </label>
                    );
                  })}
                </div>
              )}
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
