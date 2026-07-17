from __future__ import annotations

from .base import BaseRepository, utcnow_iso
from ..models.host_event import HostEvent


class HostEventRepo(BaseRepository):
    """Таймлайн статусных событий хоста, наполняется агентом."""

    model_cls = HostEvent

    def record(self, host_id: int, type: str, payload_json: str | None = None):
        return self.create(
            host_id=host_id,
            type=type,
            payload_json=payload_json,
            created_at=utcnow_iso(),
        )

    def for_host(self, host_id: int, limit: int = 200):
        rows = self._fetchall(
            "SELECT * FROM host_events WHERE host_id = ? ORDER BY id DESC LIMIT ?",
            (host_id, limit),
        )
        return [self._row_to_model(r) for r in rows]

    def recent(self, limit: int = 200):
        rows = self._fetchall(
            "SELECT * FROM host_events ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return [self._row_to_model(r) for r in rows]
