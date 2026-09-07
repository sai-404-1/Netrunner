from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from .base import BaseModel


@dataclass(slots=True)
class ScheduledTask(BaseModel):
    __table__: ClassVar[str] = 'scheduled_tasks'

    id: int | None = None
    name: str = ''
    scenario_id: int | None = None
    target_type: str = 'host'
    target_id: int | None = None
    run_at: str = ''
    is_enabled: int = 1
    last_run_at: str | None = None
    created_at: str = ''
    interval_seconds: int | None = None
    max_runs: int | None = None
    run_count: int = 0
    wait_for_online: int = 0
    # Recurring-расписание (cron по времени): days_of_week — 7-битмаска строкой,
    # позиция = weekday() (0=Пн..6=Вс), '1'=выбран день. Пусто/все нули = не расписание
    # (тогда задача разовая: run_at + при желании interval_seconds).
    # start_min/end_min/interval_min — минуты от полуночи в локальном времени сервера.
    days_of_week: str = ''
    start_min: int | None = None
    end_min: int | None = None
    interval_min: int | None = None
