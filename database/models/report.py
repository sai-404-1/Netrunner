from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from .base import BaseModel


@dataclass(slots=True)
class Report(BaseModel):
    __table__: ClassVar[str] = 'reports'

    id: int | None = None
    name: str = ''
    report_type: str = ''
    format: str = ''
    source_type: str = ''
    source_id: int | None = None
    file_path: str = ''
    summary_json: str | None = None
    created_by_task_run_id: int | None = None
    created_at: str = ''
