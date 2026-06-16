from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from .base import BaseModel


@dataclass(slots=True)
class ModuleRecord(BaseModel):
    __table__: ClassVar[str] = 'modules'

    id: int | None = None
    name: str = ''
    slug: str = ''
    module_path: str = ''
    class_name: str = ''
    repo_url: str | None = None
    is_builtin: int = 0
    is_enabled: int = 1
    description: str | None = None
    created_at: str = ''
