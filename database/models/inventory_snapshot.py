from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from .base import BaseModel


@dataclass(slots=True)
class InventorySnapshot(BaseModel):
    __table__: ClassVar[str] = 'inventory_snapshots'

    id: int | None = None
    host_id: int | None = None
    hostname: str | None = None
    os_name: str | None = None
    kernel: str | None = None
    uptime_seconds: int | None = None
    cpu_model: str | None = None
    ram_mb: int | None = None
    disks_total_gb: float | None = None
    disks_free_gb: float | None = None
    disks_count: int | None = None
    current_user: str | None = None
    package_count: int | None = None
    collected_at: str = ''
    raw_json: str | None = None
