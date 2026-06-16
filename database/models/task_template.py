from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from .base import BaseModel


@dataclass(slots=True)
class TaskTemplate(BaseModel):
    __table__: ClassVar[str] = 'task_templates'

    id: int | None = None
    name: str = ''
    module_id: int | None = None
    default_args_json: str | None = None
    description: str | None = None
    created_at: str = ''
