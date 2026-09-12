import type { Host, Group, ScheduledTask } from "./schedule-types";

export function targetsFor(type: "host" | "group", hosts: Host[], groups: Group[]) {
  return type === "host" ? hosts : groups;
}

/** Короткие имена дней недели: индекс = weekday() (0=Пн .. 6=Вс). */
export const DAY_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"] as const;

/** 7-битмаска из списка выбранных индексов дней (0=Пн). */
export function toBitmask(days: number[]): string {
  const bits = Array(7).fill("0");
  days.forEach((d) => {
    if (d >= 0 && d < 7) bits[d] = "1";
  });
  return bits.join("");
}

/** Список выбранных индексов (0=Пн) из 7-битмаски. */
export function fromBitmask(mask?: string | null): number[] {
  const out: number[] = [];
  (mask || "").split("").forEach((ch, i) => {
    if (ch === "1") out.push(i);
  });
  return out;
}

export function isEveryDay(mask?: string | null): boolean {
  return !!mask && mask.split("").every((c) => c === "1") && mask.length >= 7;
}

/** Подпись дней недели: «Каждый день», «Пн, Ср, Пт» или «—». */
export function daysLabel(days: number[]): string {
  if (days.length === 0) return "—";
  if (days.length === 7) return "Каждый день";
  return days.map((d) => DAY_SHORT[d]).join(", ");
}

/** Минуты от полуночи -> "HH:MM" (для <input type="time">). */
export function minutesToHM(min?: number | null): string {
  if (min === null || min === undefined) return "";
  const h = Math.floor(min / 60);
  const m = min % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

/** "HH:MM" -> минуты от полуночи (null если пусто/битое). */
export function hmToMinutes(v: string | null | undefined): number | null {
  if (!v) return null;
  const m = /^(\d{1,2}):(\d{1,2})$/.exec(v.trim());
  if (!m) return null;
  const h = parseInt(m[1], 10);
  const mm = parseInt(m[2], 10);
  if (mm >= 60) return null;
  return h * 60 + mm;
}

/** Хм «1:30» -> минуты (для интервала), null если некорректно. */
export function durationToMinutes(v: string | null | undefined): number | null {
  if (!v) return null;
  const m = /^(\d{1,3}):([0-5]\d)$/.exec(v.trim());
  if (!m) return null;
  return parseInt(m[1], 10) * 60 + parseInt(m[2], 10);
}

/** Человекочитаемое описание условия задачи для таблицы. */
export function scheduleLabel(t: ScheduledTask): string {
  if (t.wait_for_online) {
    return "когда будет в сети";
  }
  const days = fromBitmask(t.days_of_week);
  if (days.length > 0) {
    const from = minutesToHM(t.start_min);
    const to = minutesToHM(t.end_min);
    const iv = minutesToHM(t.interval_min);
    const day = days.length === 7 ? "каждый день" : days.map((d) => DAY_SHORT[d]).join(",");
    return `${day} ${from}–${to} / кажд ${iv}`;
  }
  // разовая по времени
  const d = new Date(t.run_at);
  if (!isNaN(d.getTime())) {
    return d.toLocaleString("ru-RU", {
      day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit",
    });
  }
  return t.run_at || "—";
}
