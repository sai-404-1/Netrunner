from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from .base import BaseModel


@dataclass(slots=True)
class SystemLog(BaseModel):
    """Запись в журнале внутренних процессов сервера («История» → «Логи»),
    не путать с host_events (статусы от агента) или task_runs (запуски модулей).
    category — открытый набор (например 'agent_install'), level — 'info'/'success'/'error'.
    """

    __table__: ClassVar[str] = 'system_logs'

    id: int | None = None
    category: str = ''
    level: str = 'info'
    message: str = ''
    host_id: int | None = None
    created_at: str = ''
