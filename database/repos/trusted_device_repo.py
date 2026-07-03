from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .base import BaseRepository, utcnow_iso
from ..models.trusted_device import TrustedDevice


class TrustedDeviceRepo(BaseRepository):
    model_cls = TrustedDevice

    def find(self, user_id: int, device_id: str):
        if not device_id:
            return None
        return self.get_one_by(user_id=user_id, device_id=device_id)

    def for_user(self, user_id: int):
        return self.filter(user_id=user_id)

    def trust(
        self,
        user_id: int,
        device_id: str,
        label: str | None = None,
        duration_sec: int | None = 3600,
        forever: bool = False,
    ):
        """Доверять устройству. `forever=True` или `duration_sec=None` → бессрочно."""
        if forever or duration_sec is None:
            until = None
        else:
            until = (
                datetime.now(timezone.utc) + timedelta(seconds=duration_sec)
            ).replace(microsecond=0).isoformat()
        now = utcnow_iso()
        existing = self.find(user_id, device_id)
        if existing:
            return self.update(
                existing.id,
                trusted_until=until,
                last_used_at=now,
                label=label or existing.label,
            )
        return self.create(
            user_id=user_id,
            device_id=device_id,
            label=label,
            trusted_until=until,
            created_at=now,
            last_used_at=now,
        )

    def touch(self, device_row_id: int):
        return self.update(device_row_id, last_used_at=utcnow_iso())

    def revoke(self, user_id: int, device_id: str) -> bool:
        row = self.find(user_id, device_id)
        if not row:
            return False
        return self.delete(row.id)
