from __future__ import annotations

from .base import BaseRepository, utcnow_iso
from ..models.user import User


class UserRepo(BaseRepository):
    model_cls = User

    def create(self, **data):
        data.setdefault('created_at', utcnow_iso())
        data.setdefault('updated_at', utcnow_iso())
        return super().create(**data)

    def update(self, item_id: int, **data):
        data.setdefault('updated_at', utcnow_iso())
        return super().update(item_id, **data)

    def by_username(self, username: str):
        return self.get_one_by(username=username)
