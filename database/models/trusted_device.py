from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from .base import BaseModel


@dataclass(slots=True)
class TrustedDevice(BaseModel):
    """Доверенное устройство пользователя (для 2FA step-up при входе).

    `trusted_until = NULL` означает бессрочное доверие («навсегда»); иначе — ISO-время,
    после которого при входе снова потребуется подтверждение через Telegram.
    """

    __table__: ClassVar[str] = 'trusted_devices'

    id: int | None = None
    user_id: int = 0
    device_id: str = ''
    label: str | None = None
    trusted_until: str | None = None
    created_at: str = ''
    last_used_at: str | None = None
