from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from .base import BaseModel


@dataclass(slots=True)
class BoardHost(BaseModel):
    __table__: ClassVar[str] = 'board_hosts'

    id: int | None = None
    board_id: int = 0
    host_id: int = 0
    x: float = 0.0
    y: float = 0.0
