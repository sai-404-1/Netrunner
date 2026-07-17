from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from .base import BaseModel


@dataclass(slots=True)
class HostEvent(BaseModel):
    """Одна запись в таймлайне статусов хоста, наполняется агентом.

    ``type`` — открытый набор: агент может присылать любой тип события (heartbeat,
    online, в будущем что-то ещё), сервер журналирует его как есть, без изменений
    кода под каждый новый тип.
    """

    __table__: ClassVar[str] = 'host_events'

    id: int | None = None
    host_id: int = 0
    type: str = ''
    payload_json: str | None = None
    created_at: str = ''
