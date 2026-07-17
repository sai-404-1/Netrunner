from __future__ import annotations

from .base import BaseRepository, utcnow_iso
from ..models.host_agent import HostAgent


class HostAgentRepo(BaseRepository):
    """Endpoint-агенты хостов. Один агент на хост (UNIQUE host_id)."""

    model_cls = HostAgent

    def by_host(self, host_id: int):
        return self.get_one_by(host_id=host_id)

    def touch(self, agent_id: int, status: str = "connected"):
        return self.update(agent_id, status=status, last_seen_at=utcnow_iso())

    def mark_disconnected(self, agent_id: int):
        return self.update(agent_id, status="disconnected")
