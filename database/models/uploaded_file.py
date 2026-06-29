from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from .base import BaseModel


@dataclass(slots=True)
class UploadedFile(BaseModel):
    __table__: ClassVar[str] = 'uploaded_files'

    id: int | None = None
    original_name: str = ''
    stored_path: str = ''
    size_bytes: int = 0
    uploaded_by: str | None = None
    created_at: str = ''
