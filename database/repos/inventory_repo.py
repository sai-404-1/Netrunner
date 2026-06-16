from __future__ import annotations

from .base import BaseRepository, utcnow_iso
from ..models.inventory_snapshot import InventorySnapshot


class InventoryRepo(BaseRepository):
    model_cls = InventorySnapshot

    def create(self, **data):
        data.setdefault('collected_at', utcnow_iso())
        return super().create(**data)

    def latest_for_host(self, host_id: int):
        row = self._fetchone(
            'SELECT * FROM inventory_snapshots WHERE host_id = ? ORDER BY collected_at DESC LIMIT 1',
            (host_id,),
        )
        return self._row_to_model(row)

    def history_for_host(self, host_id: int, limit: int = 20):
        rows = self._fetchall(
            'SELECT * FROM inventory_snapshots WHERE host_id = ? ORDER BY collected_at DESC LIMIT ?',
            (host_id, limit),
        )
        return [self._row_to_model(row) for row in rows]

    def latest_per_host(self):
        rows = self._fetchall(
            """
            SELECT s.*
            FROM inventory_snapshots s
            INNER JOIN (
                SELECT host_id, MAX(collected_at) AS max_collected_at
                FROM inventory_snapshots
                GROUP BY host_id
            ) latest ON latest.host_id = s.host_id AND latest.max_collected_at = s.collected_at
            ORDER BY s.host_id
            """,
            (),
        )
        return [self._row_to_model(row) for row in rows]
