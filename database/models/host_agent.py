from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from .base import BaseModel


@dataclass(slots=True)
class HostAgent(BaseModel):
    """Endpoint-агент хоста: report-only, сам звонит на сервер по WebSocket."""

    __table__: ClassVar[str] = 'host_agents'

    id: int | None = None
    host_id: int = 0
    ssh_username: str = ''
    token_encrypted: str = ''
    private_key_encrypted: str = ''
    public_key: str = ''
    status: str = 'provisioned'
    last_seen_at: str | None = None
    created_at: str = ''
