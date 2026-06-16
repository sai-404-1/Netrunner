from __future__ import annotations

from .base import BaseRepository, utcnow_iso
from ..models.report import Report


class ReportRepo(BaseRepository):
    model_cls = Report

    def create(self, **data):
        data.setdefault('created_at', utcnow_iso())
        return super().create(**data)

    def latest(self, limit: int = 20, report_type: str | None = None):
        if report_type:
            rows = self._fetchall(
                'SELECT * FROM reports WHERE report_type = ? ORDER BY created_at DESC LIMIT ?',
                (report_type, limit),
            )
        else:
            rows = self._fetchall(
                'SELECT * FROM reports ORDER BY created_at DESC LIMIT ?',
                (limit,),
            )
        return [self._row_to_model(row) for row in rows]

    def clear_all(self):
        self.conn.execute('DELETE FROM reports')
        self.conn.commit()
        return True
