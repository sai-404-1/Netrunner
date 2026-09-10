from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from .base import BaseModel


@dataclass(slots=True)
class TaskRun(BaseModel):
    __table__: ClassVar[str] = 'task_runs'

    id: int | None = None
    module_id: int | None = None
    target_type: str = 'host'
    target_id: int | None = None
    args_json: str | None = None
    status: str = 'pending'
    stdout_text: str | None = None
    stderr_text: str | None = None
    exit_code: int | None = None
    per_host_json: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    trigger_type: str = 'manual'
    created_by: str | None = None
