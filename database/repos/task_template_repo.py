from __future__ import annotations

from .base import BaseRepository, utcnow_iso
from ..models.task_template import TaskTemplate


class TaskTemplateRepo(BaseRepository):
    model_cls = TaskTemplate

    def create(self, **data):
        data.setdefault('created_at', utcnow_iso())
        return super().create(**data)
