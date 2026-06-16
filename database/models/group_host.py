from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from .base import BaseModel


@dataclass(slots=True)
class GroupHost(BaseModel):
    __table__: ClassVar[str] = 'group_hosts'
    __pk__: ClassVar[str] = 'group_id'

    group_id: int | None = None
    host_id: int | None = None
