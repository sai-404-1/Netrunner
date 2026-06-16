from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from .base import BaseModel


@dataclass(slots=True)
class SSHKey(BaseModel):
    __table__: ClassVar[str] = 'ssh_keys'

    id: int | None = None
    name: str = ''
    private_key_path: str = ''
    public_key_path: str | None = None
    key_type: str | None = None
    public_key: str | None = None
    private_key: str | None = None
    fingerprint: str | None = None
    has_passphrase: int = 0
    passphrase_hint: str | None = None
    created_at: str = ''
    expires_at: str | None = None
    is_default: int = 0
