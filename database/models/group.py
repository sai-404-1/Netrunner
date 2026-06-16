from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from .base import BaseModel


@dataclass(slots=True)
class Group(BaseModel):
    __table__: ClassVar[str] = 'groups'

    id: int | None = None
    name: str = ''
    kind: str = 'custom'
    description: str | None = None
    created_at: str = ''
