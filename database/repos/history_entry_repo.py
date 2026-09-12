from __future__ import annotations

from .base import BaseRepository, utcnow_iso
from ..models.history_entry import HistoryEntry


class HistoryEntryRepo(BaseRepository):
    """Единая лента «История» (history_entries) — сервисные события NetRunner."""

    model_cls = HistoryEntry
    table_name = 'history_entries'

    def record(
        self,
        source: str,
        event_type: str,
        title: str,
        *,
        actor_name: str | None = None,
        actor_id: int | None = None,
        description: str | None = None,
        level: str = 'info',
        payload: dict | None = None,
        ref_type: str | None = None,
        ref_id: int | None = None,
        host_id: int | None = None,
    ):
        import json

        return self.create(
            source=source,
            event_type=event_type,
            actor_name=actor_name,
            actor_id=actor_id,
            title=title,
            description=description,
            level=level,
            payload_json=json.dumps(payload, ensure_ascii=False) if payload else None,
            ref_type=ref_type,
            ref_id=ref_id,
            host_id=host_id,
            created_at=utcnow_iso(),
        )

    def recent(self, limit: int = 200, sources: list[str] | None = None, offset: int = 0):
        """Последние записи, опционально отфильтрованные по source-слагам и
        с пагинацией (offset/limit)."""
        if sources:
            placeholders = ', '.join('?' for _ in sources)
            rows = self._fetchall(
                f"SELECT * FROM {self.table_name} "
                f"WHERE source IN ({placeholders}) ORDER BY id DESC LIMIT ? OFFSET ?",
                (*sources, limit, offset),
            )
        else:
            rows = self._fetchall(
                f"SELECT * FROM {self.table_name} ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
        return [self._row_to_model(r) for r in rows]

    def count(self, sources: list[str] | None = None) -> int:
        """Общее число записей (для пагинации), опционально по source-слагам."""
        if sources:
            placeholders = ', '.join('?' for _ in sources)
            row = self._fetchone(
                f"SELECT COUNT(*) FROM {self.table_name} WHERE source IN ({placeholders})",
                tuple(sources),
            )
        else:
            row = self._fetchone(f"SELECT COUNT(*) FROM {self.table_name}")
        return row[0] if row else 0
