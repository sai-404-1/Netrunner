from __future__ import annotations

from .base import BaseRepository, utcnow_iso
from ..models.task_run import TaskRun


class TaskRunRepo(BaseRepository):
    model_cls = TaskRun

    def create(self, **data):
        data.setdefault('status', 'pending')
        data.setdefault('trigger_type', 'manual')
        return super().create(**data)

    def start(self, module_id: int, target_type: str, target_id: int, created_by: str | None = None, **extra):
        payload = {
            'module_id': module_id,
            'target_type': target_type,
            'target_id': target_id,
            'status': 'running',
            'started_at': utcnow_iso(),
            'created_by': created_by,
        }
        payload.update(extra)
        return self.create(**payload)

    def finish(
        self,
        run_id: int,
        status: str,
        stdout_text: str | None = None,
        stderr_text: str | None = None,
        exit_code: int | None = None,
        per_host_json: str | None = None,
    ):
        return self.update(
            run_id,
            status=status,
            stdout_text=stdout_text,
            stderr_text=stderr_text,
            exit_code=exit_code,
            per_host_json=per_host_json,
            finished_at=utcnow_iso(),
        )

    def list_recent(self, limit: int = 50):
        rows = self._fetchall(
            'SELECT * FROM task_runs ORDER BY id DESC LIMIT ?',
            (limit,),
        )
        return [self._row_to_model(row) for row in rows]

    def clear_all(self):
        self.conn.execute('DELETE FROM task_runs', ())
        self.conn.execute("DELETE FROM sqlite_sequence WHERE name='task_runs'", ())
        self.conn.commit()
        return True
