from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from .base import BaseModel


@dataclass(slots=True)
class HostDefaultCredentials(BaseModel):
    __table__: ClassVar[str] = 'host_default_credentials'
    id: int | None = None
    username: str = ''
    password_encrypted: str = ''
    last_updated_at: str = ''
