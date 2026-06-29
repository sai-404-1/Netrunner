from __future__ import annotations

from .base import BaseRepository, utcnow_iso
from ..models.uploaded_file import UploadedFile


class UploadedFileRepo(BaseRepository):
    model_cls = UploadedFile

    def create(self, **data):
        data.setdefault('created_at', utcnow_iso())
        data.setdefault('size_bytes', 0)
        return super().create(**data)

    def recent(self, limit: int = 200):
        rows = self._fetchall(
            'SELECT * FROM uploaded_files ORDER BY created_at DESC, id DESC LIMIT ?',
            (limit,),
        )
        return [self._row_to_model(row) for row in rows]
