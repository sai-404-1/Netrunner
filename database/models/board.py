from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from .base import BaseModel


@dataclass(slots=True)
class Board(BaseModel):
    __table__: ClassVar[str] = 'boards'

    id: int | None = None
    name: str = ''
    owner_user_id: int = 0
    width: int = 1600
    height: int = 900
    created_at: str = ''
    updated_at: str = ''
