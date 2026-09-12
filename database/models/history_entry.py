from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from .base import BaseModel


@dataclass(slots=True)
class HistoryEntry(BaseModel):
    """Запись в единой ленте «История» (history_entries).

    source — slug зарегистрированного сервиса (scenario/task/agent/
    agent_message/scheduler). Не путать с system_logs (программные логи кода)
    или task_runs/scenario_runs (рабочие таблицы исполнения). payload_json —
    специфичные поля, которые сервис сам решил записать (колонки из его
    реестра). actor_name — снапшот имени инициатора (не FK, переживает
    переименование/удаление пользователя).
    """

    __table__: ClassVar[str] = 'history_entries'

    id: int | None = None
    source: str = ''
    event_type: str = ''
    actor_name: str | None = None
    actor_id: int | None = None
    title: str = ''
    description: str | None = None
    level: str = 'info'
    payload_json: str | None = None
    ref_type: str | None = None
    ref_id: int | None = None
    host_id: int | None = None
    created_at: str = ''
