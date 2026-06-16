from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from .base import BaseModel


@dataclass(slots=True)
class User(BaseModel):
    __table__: ClassVar[str] = 'users'

    id: int | None = None
    username: str = ''
    email: str | None = None
    password_hash: str = ''
    is_active: int = 1
    is_superuser: int = 0
    token: str | None = None
    created_at: str = ''
    updated_at: str = ''
