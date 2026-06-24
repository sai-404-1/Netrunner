from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from .base import BaseModel


@dataclass(slots=True)
class UserGroupAccess(BaseModel):
    __table__: ClassVar[str] = 'user_group_access'

    id: int | None = None
    user_id: int = 0
    group_id: int = 0
