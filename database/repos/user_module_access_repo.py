from __future__ import annotations

from .base import BaseRepository
from ..models.user_module_access import UserModuleAccess


class UserModuleAccessRepo(BaseRepository):
    model_cls = UserModuleAccess

    def by_user(self, user_id: int) -> list[UserModuleAccess]:
        return self.filter(user_id=user_id)

    def by_user_module(self, user_id: int, module_id: int) -> UserModuleAccess | None:
        return self.get_one_by(user_id=user_id, module_id=module_id)

    def set_access(self, user_id: int, module_id: int, allowed: int) -> UserModuleAccess:
        existing = self.by_user_module(user_id, module_id)
        if existing:
            return self.update(existing.id, allowed=allowed)
        return self.create(user_id=user_id, module_id=module_id, allowed=allowed)

    def clear_user(self, user_id: int) -> int:
        cur = self.conn.execute(
            f'DELETE FROM {self.table_name} WHERE user_id = ?', (user_id,)
        )
        self.conn.commit()
        return cur.rowcount
