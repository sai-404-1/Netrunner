from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .base import BaseRepository, utcnow_iso
from ..models.scheduled_task import ScheduledTask


class ScheduledTaskRepo(BaseRepository):
    model_cls = ScheduledTask

    def create(self, **data):
        data.setdefault('created_at', utcnow_iso())
        data.setdefault('is_enabled', 1)
        data.setdefault('run_count', 0)
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
        task = self.get(task_id)
        if task is None:
            return None

        now_str = when or utcnow_iso()
        new_run_count = (task.run_count or 0) + 1

        if task.interval_seconds:
            # Recurring task: schedule the next run
            now_dt = datetime.now(timezone.utc)
            next_dt = now_dt + timedelta(seconds=task.interval_seconds)
            next_run_at = next_dt.replace(microsecond=0).isoformat()

            max_runs = task.max_runs
            if max_runs is not None and new_run_count >= max_runs:
                # Reached the run limit — disable
                return self.update(
                    task_id,
                    last_run_at=now_str,
                    run_count=new_run_count,
                    is_enabled=0,
                )
            else:
                return self.update(
                    task_id,
                    last_run_at=now_str,
                    run_at=next_run_at,
                    run_count=new_run_count,
                    is_enabled=1,
                )
        else:
            # One-shot task: disable after first run
            return self.update(
                task_id,
                last_run_at=now_str,
                run_count=new_run_count,
                is_enabled=0,
            )
