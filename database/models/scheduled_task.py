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
