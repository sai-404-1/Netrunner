from __future__ import annotations

from .base import BaseRepository, utcnow_iso
from ..models.group import Group
from ..models.group_host import GroupHost
from ..models.host import Host


class GroupRepo(BaseRepository):
    model_cls = Group

    def create(self, **data):
        data.setdefault('created_at', utcnow_iso())
        data.setdefault('kind', 'custom')
        return super().create(**data)

    def add_host(self, group_id: int, host_id: int) -> GroupHost:
        self.conn.execute(
            'INSERT OR IGNORE INTO group_hosts (group_id, host_id) VALUES (?, ?)',
            (group_id, host_id),
        )
        self.conn.commit()
        return GroupHost(group_id=group_id, host_id=host_id)

    def remove_host(self, group_id: int, host_id: int) -> bool:
        cur = self.conn.execute(
            'DELETE FROM group_hosts WHERE group_id = ? AND host_id = ?',
            (group_id, host_id),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def hosts(self, group_id: int):
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
        return [Host.from_row(row) for row in rows]

    def first_group_id_for_host(self, host_id: int):
        row = self._fetchone(
            'SELECT group_id FROM group_hosts WHERE host_id = ? ORDER BY group_id LIMIT 1',
            (host_id,),
        )
        return row['group_id'] if row else None

    def first_group_for_host(self, host_id: int):
        row = self._fetchone(
            """
            SELECT g.* FROM groups g
            JOIN group_hosts gh ON gh.group_id = g.id
            WHERE gh.host_id = ?
            ORDER BY g.id LIMIT 1
            """,
            (host_id,),
        )
        return self._row_to_model(row) if row else None
