from __future__ import annotations

from .base import BaseRepository, utcnow_iso
from ..models.host import Host


class HostRepo(BaseRepository):
    model_cls = Host

    def create(self, **data):
        now = utcnow_iso()
        data.setdefault('created_at', now)
        data.setdefault('updated_at', now)
        data.setdefault('is_active', 1)
        data.setdefault('port', 22)
        return super().create(**data)

    def update(self, item_id: int, **data):
        data['updated_at'] = utcnow_iso()
        return super().update(item_id, **data)

    def by_group(self, group_id: int):
        rows = self._fetchall(
            """
            SELECT h.*
            FROM hosts h
            INNER JOIN group_hosts gh ON gh.host_id = h.id
            WHERE gh.group_id = ?
            ORDER BY h.name
            """,
            (group_id,),
        )
        return [self._row_to_model(row) for row in rows]

    def touch_seen(self, host_id: int, when: str | None = None):
        return self.update(host_id, last_seen_at=when or utcnow_iso())
