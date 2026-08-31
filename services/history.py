from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ServiceRegistration:
    """Контракт сервиса в единой истории.

    Каждый сервис NetRunner (сценарии, TaskRunner, агент, планировщик...)
    регистрируется в реестре один раз, прописывая сам:
    - slug        — латинский уникальный идентификатор (scenario, task, ...)
    - name        — человеческое имя («Сценарии», «Задачи», ...)
    - level       — важность по умолчанию (info/success/error)
    - columns     — какие поля payload показывать колонками в таблице:
                    [(key, label), ...] — key — ключ в payload, label — заголовок
    - event_types — какие виды событий умеет порождать сервис (для подробностей)
    """

    slug: str
    name: str
    columns: list[tuple[str, str]] = field(default_factory=list)
    level: str = 'info'
    event_types: dict[str, dict[str, Any]] = field(default_factory=dict)


class HistoryService:
    """Точка входа в единую историю. Любой сервис пишет через record(); реестр
    сервисов отдаётся фронту по API — фильтры и колонки строятся динамически."""

    def __init__(self, db):
        self._db = db
        self._services: dict[str, ServiceRegistration] = {}
        self._register_defaults()

    # ---- реестр ----

    def _register_defaults(self):
        self.register(
            ServiceRegistration(
                slug='scenario',
                name='Сценарии',
                level='info',
                columns=[
                    ('scenario_name', 'Сценарий'),
                    ('hosts_count', 'Хостов'),
                ],
                event_types={
                    'scenario_run': {'label': 'Запуск сценария', 'level': 'info'},
                    'scenario_run_done': {'label': 'Завершение сценария', 'level': 'success'},
                    'scenario_step_failed': {'label': 'Шаг сценария: ошибка', 'level': 'error'},
                    'scenario_failed': {'label': 'Сценарий завершён с ошибкой', 'level': 'error'},
                },
            )
        )
        self.register(
            ServiceRegistration(
                slug='task',
                name='Задачи',
                level='info',
                columns=[
                    ('module_name', 'Модуль'),
                    ('target', 'Цель'),
                ],
                event_types={
                    'task_run': {'label': 'Запуск модуля', 'level': 'info'},
                    'task_done': {'label': 'Задача завершена', 'level': 'success'},
                    'task_failed': {'label': 'Задача завершена с ошибкой', 'level': 'error'},
                },
            )
        )
        self.register(
            ServiceRegistration(
                slug='agent',
                name='Агент',
                level='info',
                columns=[
                    ('host_name', 'Хост'),
                    ('action', 'Действие'),
                ],
                event_types={
                    'agent_install': {'label': 'Установка агента', 'level': 'success'},
                    'agent_reinstall': {'label': 'Переустановка агента', 'level': 'info'},
                    'agent_error': {'label': 'Ошибка агента', 'level': 'error'},
                },
            )
        )
        self.register(
            ServiceRegistration(
                slug='agent_message',
                name='Сообщения агента',
                level='info',
                columns=[
                    ('host_name', 'Хост'),
                    ('message_type', 'Тип'),
                ],
                event_types={
                    'agent_msg': {'label': 'Сообщение от агента', 'level': 'info'},
                },
            )
        )
        self.register(
            ServiceRegistration(
                slug='scheduler',
                name='Планировщик',
                level='info',
                columns=[
                    ('task_name', 'Задача'),
                    ('hosts_count', 'Хостов'),
                ],
                event_types={
                    'scheduler_run': {'label': 'Автозапуск по расписанию', 'level': 'info'},
                    'scheduler_done': {'label': 'Автозапуск завершён', 'level': 'success'},
                    'scheduler_failed': {'label': 'Автозапуск завершён с ошибкой', 'level': 'error'},
                },
            )
        )

    def register(self, reg: ServiceRegistration):
        if not reg.slug or not reg.name:
            raise ValueError('ServiceRegistration requires slug and name')
        self._services[reg.slug] = reg

    def unregister(self, slug: str):
        self._services.pop(slug, None)

    def services(self) -> list[ServiceRegistration]:
        """Зарегистрированные сервисы в порядке добавления (стабильный порядок)."""
        return list(self._services.values())

    def get(self, slug: str) -> ServiceRegistration | None:
        return self._services.get(slug)

    def registry_payload(self) -> list[dict]:
        """Сериализация реестра для фронта: кнопки-фильтры + колонки."""
        out = []
        for reg in self.services():
            out.append({
                'slug': reg.slug,
                'name': reg.name,
                'level': reg.level,
                'columns': [{'key': k, 'label': label} for k, label in reg.columns],
                'event_types': {
                    et: {'label': cfg.get('label', et), 'level': cfg.get('level', 'info')}
                    for et, cfg in reg.event_types.items()
                },
            })
        return out

    # ---- запись ----

    def record(
        self,
        source: str,
        event_type: str,
        title: str,
        *,
        actor_name: str | None = None,
        actor_id: int | None = None,
        description: str | None = None,
        level: str | None = None,
        payload: dict[str, Any] | None = None,
        ref_type: str | None = None,
        ref_id: int | None = None,
        host_id: int | None = None,
    ):
        """Единственная точка входа: сервис пишет событие в общую историю."""
        if source not in self._services:
            raise ValueError(f"Unknown history source: {source!r}. Register service first.")
        if level is None:
            reg = self._services[source]
            et_cfg = reg.event_types.get(event_type)
            level = (et_cfg or {}).get('level') or reg.level
        return self._db.history_entries.record(
            source=source,
            event_type=event_type,
            title=title,
            actor_name=actor_name,
            actor_id=actor_id,
            description=description,
            level=level,
            payload=payload,
            ref_type=ref_type,
            ref_id=ref_id,
            host_id=host_id,
        )

    def list(self, limit: int = 200, sources: list[str] | None = None, offset: int = 0):
        return self._db.history_entries.recent(limit=limit, sources=sources, offset=offset)

    def count(self, sources: list[str] | None = None) -> int:
        return self._db.history_entries.count(sources=sources)

    def get_entry(self, entry_id: int):
        return self._db.history_entries.get(entry_id)

    def to_dict(self, entry) -> dict[str, Any]:
        """Запись → dict для фронта: payload распарсен, колонки подставлены из реестра."""
        payload = {}
        if entry.payload_json:
            try:
                payload = json.loads(entry.payload_json)
            except (json.JSONDecodeError, TypeError):
                payload = {}
        reg = self._services.get(entry.source)
        columns = []
        if reg:
            for key, label in reg.columns:
                columns.append({'key': key, 'label': label, 'value': payload.get(key)})
        return {
            'id': entry.id,
            'source': entry.source,
            'source_name': reg.name if reg else entry.source,
            'event_type': entry.event_type,
            'event_label': (reg.event_types.get(entry.event_type) or {}).get('label', entry.event_type)
            if reg else entry.event_type,
            'actor_name': entry.actor_name,
            'actor_id': entry.actor_id,
            'title': entry.title,
            'description': entry.description,
            'level': entry.level,
            'payload': payload,
            'columns': columns,
            'ref_type': entry.ref_type,
            'ref_id': entry.ref_id,
            'host_id': entry.host_id,
            'created_at': entry.created_at,
        }
