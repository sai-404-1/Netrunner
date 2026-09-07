from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .base import BaseRepository, utcnow_iso
from ..models.scheduled_task import ScheduledTask

# Жёсткий минимум интервала recurring-расписания (в минутах): меньше нельзя —
# интервал 0 = бесконечный цикл срабатываний каждую итерацию планировщика, что
# убьёт систему форками. Сай: «каждую долю секунды форк планировщика — это убьёт
# систему, жёстко ограничить». Значения приходят с фронта «Каждые Ч:ММ».
MIN_REPEAT_MINUTES = 1


def is_schedule(task) -> bool:
    """True, если задача — recurring-расписание (cron): задан хоть один день."""
    return any(ch == '1' for ch in (task.days_of_week or ''))


def validate_schedule(days_of_week: str, start_min, end_min, interval_min) -> None:
    """Валидация recurring-расписания. Бросает ValueError с причиной.

    Правила:
      - days_of_week — 7-битмаска ('1'/'0'), позиция = weekday() (0=Пн..6=Вс);
      - должен быть выбран хотя бы один день;
      - окно непустое и корректное: 0 <= start_min < end_min <= 1439;
      - интервал не меньше MIN_REPEAT_MINUTES (защита от бесконечного цикла);
      - интервал не длиннее окна (иначе срабатывает максимум 1 раз за окно — лишено
        смысла для расписания; для «раз в N, когда комп онлайн» есть другие механизмы).
    """
    days = (days_of_week or '').strip()
    if not days or len(days) != 7 or not all(ch in '01' for ch in days):
        raise ValueError("days_of_week должен быть 7-битмаской из '0'/'1'")
    if not any(ch == '1' for ch in days):
        raise ValueError("Выберите хотя бы один день запуска")
    if start_min is None or end_min is None or interval_min is None:
        raise ValueError("Для расписания нужны start_min, end_min, interval_min")
    if not (0 <= start_min < end_min <= 1439):
        raise ValueError("Некорректное окно запуска: 0 <= С < До <= 23:59")
    if interval_min < MIN_REPEAT_MINUTES:
        raise ValueError(
            f"Интервал слишком мал: минимум {MIN_REPEAT_MINUTES} минута "
            f"(значение {interval_min}). Ноль запрещён — он дал бы бесконечный цикл."
        )
    if interval_min > (end_min - start_min):
        raise ValueError(
            "Интервал не должен быть длиннее окна запуска (иначе будет "
            "максимум одно срабатывание за окно)"
        )


def _slot_times(start_min: int, end_min: int, interval_min: int, day_start: datetime):
    """Моменты слотов в окне [start_min, end_min] с шагом interval_min (end включён)."""
    minute = start_min
    while minute <= end_min:
        yield day_start + timedelta(minutes=minute)
        minute += interval_min


def next_slot_local(after: datetime, task) -> datetime | None:
    """Ближайший слот расписания строго ПОСЛЕ `after` (tz-aware, локальное время).

    Перебирает до 7 дней вперёд (должен хватить, раз хоть один день выбран).
    Возвращает локальный datetime или None, если расписание не даёт слотов.
    """
    days = (task.days_of_week or '')
    start_min, end_min, interval_min = task.start_min, task.end_min, task.interval_min
    if start_min is None or end_min is None or not interval_min:
        return None
    for offset in range(0, 8):
        day = after.date() + timedelta(days=offset)
        if day.weekday() >= len(days) or days[day.weekday()] != '1':
            continue
        day_start = datetime(day.year, day.month, day.day, tzinfo=after.tzinfo)
        for slot in _slot_times(start_min, end_min, interval_min, day_start):
            if slot > after:
                return slot
    return None


def next_slot_utc_iso(after_local: datetime, task) -> str | None:
    """Следующий слот после `after_local`, как UTC ISO-строка для run_at."""
    slot = next_slot_local(after_local, task)
    if slot is None:
        return None
    return slot.astimezone(timezone.utc).replace(microsecond=0).isoformat()


class ScheduledTaskRepo(BaseRepository):
    model_cls = ScheduledTask

    def create(self, **data):
        data.setdefault('created_at', utcnow_iso())
        data.setdefault('is_enabled', 1)
        data.setdefault('run_count', 0)
        data.setdefault('days_of_week', '')
        return super().create(**data)

    def due(self, before_iso: str | None = None):
        before = before_iso or utcnow_iso()
        rows = self._fetchall(
            """
            SELECT * FROM scheduled_tasks
            WHERE is_enabled = 1
              AND (
                wait_for_online = 1
                OR run_at <= ?
              )
            ORDER BY run_at ASC
            """,
            (before,),
        )
        return [self._row_to_model(row) for row in rows]

    def mark_ran(self, task_id: int, when: str | None = None):
        task = self.get(task_id)
        if task is None:
            return None

        now_str = when or utcnow_iso()
        new_run_count = (task.run_count or 0) + 1

        # Recurring-расписание (cron): сдвигаем run_at на следующий слот расписания.
        # Пропущенные за время выполнения слоты не «догоняются» — это расписание,
        # а не очередь; для «выполнить когда цель в сети» есть wait_for_online.
        if is_schedule(task):
            now_local = datetime.now().astimezone()
            next_run = next_slot_utc_iso(now_local, task)
            max_runs = task.max_runs
            if next_run is None or (max_runs is not None and new_run_count >= max_runs):
                # Нет валидных слотов впереди либо достигнут лимит — отключаем.
                return self.update(
                    task_id,
                    last_run_at=now_str,
                    run_count=new_run_count,
                    is_enabled=0,
                )
            return self.update(
                task_id,
                last_run_at=now_str,
                run_at=next_run,
                run_count=new_run_count,
                is_enabled=1,
            )

        if task.interval_seconds:
            # Простое повторение «раз в N секунд» (устаревший путь, без дней/окна).
            now_dt = datetime.now(timezone.utc)
            next_dt = now_dt + timedelta(seconds=task.interval_seconds)
            next_run_at = next_dt.replace(microsecond=0).isoformat()

            max_runs = task.max_runs
            if max_runs is not None and new_run_count >= max_runs:
                # Reached the run limit — disable
                return self.update(
                    task_id,
                    last_run_at=now_str,
                    run_count=new_run_count,
                    is_enabled=0,
                )
            else:
                return self.update(
                    task_id,
                    last_run_at=now_str,
                    run_at=next_run_at,
                    run_count=new_run_count,
                    is_enabled=1,
                )
        else:
            # One-shot task: disable after first run
            return self.update(
                task_id,
                last_run_at=now_str,
                run_count=new_run_count,
                is_enabled=0,
            )
