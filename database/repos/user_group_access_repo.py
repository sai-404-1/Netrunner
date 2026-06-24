from __future__ import annotations

from .base import BaseRepository
from ..models.user_group_access import UserGroupAccess


class UserGroupAccessRepo(BaseRepository):
    model_cls = UserGroupAccess

    def by_user(self, user_id: int) -> list[UserGroupAccess]:
        return self.filter(user_id=user_id)

    def has_access(self, user_id: int, group_id: int) -> bool:
        return self.get_one_by(user_id=user_id, group_id=group_id) is not None

    def set_access(self, user_id: int, group_id: int, granted: bool) -> None:
        existing = self.get_one_by(user_id=user_id, group_id=group_id)
        if granted and not existing:
            self.create(user_id=user_id, group_id=group_id)
        elif not granted and existing:
            self.delete(existing.id)

    def clear_user(self, user_id: int) -> int:
        cur = self.conn.execute(
            f'DELETE FROM {self.table_name} WHERE user_id = ?', (user_id,)
        )
        self.conn.commit()
        return cur.rowcount
