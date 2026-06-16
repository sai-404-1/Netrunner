from __future__ import annotations

from .base import BaseRepository, utcnow_iso
from ..models.module_record import ModuleRecord


class ModuleRepo(BaseRepository):
    model_cls = ModuleRecord

    def create(self, **data):
        data.setdefault('created_at', utcnow_iso())
        data.setdefault('is_builtin', 0)
        data.setdefault('is_enabled', 1)
        return super().create(**data)

    def enabled(self):
        return self.filter(is_enabled=1)

    def builtin(self):
        return self.filter(is_builtin=1)

    def by_slug(self, slug: str):
        return self.get_one_by(slug=slug)
