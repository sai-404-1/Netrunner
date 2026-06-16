from __future__ import annotations

from .base import BaseRepository, utcnow_iso
from ..models.scheduled_task import ScheduledTask


class ScheduledTaskRepo(BaseRepository):
    model_cls = ScheduledTask

    def create(self, **data):
        data.setdefault('created_at', utcnow_iso())
        data.setdefault('is_enabled', 1)
        return super().create(**data)

    def due(self, before_iso: str | None = None):
        before = before_iso or utcnow_iso()
        rows = self._fetchall(
            """
            SELECT * FROM scheduled_tasks
            WHERE is_enabled = 1 AND run_at <= ?
            ORDER BY run_at ASC
            """,
            (before,),
        )
        return [self._row_to_model(row) for row in rows]

    def mark_ran(self, task_id: int, when: str | None = None):
        return self.update(
            task_id,
            last_run_at=when or utcnow_iso(),
            is_enabled=0,
        )
