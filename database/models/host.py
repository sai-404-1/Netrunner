from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from .base import BaseModel


@dataclass(slots=True)
class Host(BaseModel):
    __table__: ClassVar[str] = 'hosts'

    id: int | None = None
    name: str = ''
    address: str = ''
    port: int = 22
    username: str = ''
    ssh_key_id: int | None = None
    description: str | None = None
    is_active: int = 1
    last_seen_at: str | None = None
    created_at: str = ''
    updated_at: str = ''
