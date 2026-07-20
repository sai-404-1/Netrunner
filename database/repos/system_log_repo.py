from __future__ import annotations

from .base import BaseRepository, utcnow_iso
from ..models.system_log import SystemLog


class SystemLogRepo(BaseRepository):
    """Журнал внутренних процессов сервера (вкладка «Логи»)."""

    model_cls = SystemLog

    def record(self, category: str, level: str, message: str, host_id: int | None = None):
        return self.create(
            category=category,
            level=level,
            message=message,
            host_id=host_id,
            created_at=utcnow_iso(),
        )

    def recent(self, limit: int = 200):
        rows = self._fetchall(
            "SELECT * FROM system_logs ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return [self._row_to_model(r) for r in rows]
