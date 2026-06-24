from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from .base import BaseModel


@dataclass(slots=True)
class UserModuleAccess(BaseModel):
    __table__: ClassVar[str] = 'user_module_access'

    id: int | None = None
    user_id: int = 0
    module_id: int = 0
    allowed: int = 1
