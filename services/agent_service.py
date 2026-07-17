"""Endpoint-агент хоста — report-only, сам открывает исходящее WS-соединение к
NetRunner (звонит домой): работает через NAT, на хосте не нужно открывать порты,
сервер не подключается внутрь.

Этот сервис отвечает за секреты/статус агента и журнал его событий. Сама установка
на хосте (создание сервисного пользователя, копирование скрипта и systemd-юнита,
запуск) — отдельный шаг, модуль ``computer/module/agent_provision.py``, выполняется
через уже существующий обычный SSH-канал.

Два разных секрета для разных целей: SSH-ключ сервисного пользователя (канал
восстановления через SSH, если токен/агент когда-нибудь потребуется перевыпустить)
и отдельный bearer-токен (аутентификация самого WS-соединения) — компрометация
одного не вскрывает другой.

Канал компьютер → сервер — только статусы/телеметрия, никогда команды на
исполнение (см. record_event: это открытый журнал, не диспетчер команд). Канал
сервер → агент — тоже report-only: сервер не шлёт агенту ничего, кроме закрытия
соединения при невалидном токене (см. agent_websocket_handler в webui/server.py).
"""

from __future__ import annotations

import secrets

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from database.repos.base import utcnow_iso
from services.secrets import decrypt_secret, encrypt_secret

DEFAULT_SSH_USERNAME = "netrunner-svc"


def _generate_keypair() -> tuple[str, str]:
    """ED25519-пара для сервисного SSH-пользователя. Без пароля/passphrase — ключ
    и так хранится в шифре на сервере, не на диске хоста в открытом виде."""
    private_key = ed25519.Ed25519PrivateKey.generate()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.OpenSSH,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_openssh = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH,
    ).decode("utf-8")
    return private_pem, public_openssh


class AgentService:
    def __init__(self, db):
        self.db = db

    def provision(self, host_id: int, ssh_username: str = DEFAULT_SSH_USERNAME) -> dict:
        """(Пере-)генерирует секреты агента для хоста и сохраняет их. Не трогает
        сеть — вызывающий (модуль agent_provision) сам копирует ключ/токен на хост."""
        private_pem, public_openssh = _generate_keypair()
        token = secrets.token_urlsafe(32)
        existing = self.db.host_agents.by_host(host_id)
        data = dict(
            ssh_username=ssh_username,
            token_encrypted=encrypt_secret(token),
            private_key_encrypted=encrypt_secret(private_pem),
            public_key=public_openssh,
            status="provisioned",
        )
        if existing:
            agent = self.db.host_agents.update(existing.id, **data)
        else:
            agent = self.db.host_agents.create(
                host_id=host_id, created_at=utcnow_iso(), last_seen_at=None, **data
            )
        return {
            "agent_id": agent.id,
            "ssh_username": agent.ssh_username,
            "public_key": agent.public_key,
            "token": token,  # только сейчас, в открытом виде — вызывающий копирует на хост и забывает
            "private_key": private_pem,
        }

    def get_status(self, host_id: int) -> dict | None:
        agent = self.db.host_agents.by_host(host_id)
        if not agent:
            return None
        return {
            "status": agent.status,
            "ssh_username": agent.ssh_username,
            "last_seen_at": agent.last_seen_at,
        }

    def verify_token(self, host_id: int, token: str) -> bool:
        agent = self.db.host_agents.by_host(host_id)
        if not agent or not token:
            return False
        try:
            return secrets.compare_digest(decrypt_secret(agent.token_encrypted), token)
        except Exception:  # noqa: BLE001 — повреждённый секрет = отказ, не падение
            return False

    def record_connect(self, host_id: int) -> None:
        agent = self.db.host_agents.by_host(host_id)
        if agent:
            self.db.host_agents.touch(agent.id, status="connected")
            self.db.host_events.record(host_id, "agent_connected")

    def record_disconnect(self, host_id: int) -> None:
        agent = self.db.host_agents.by_host(host_id)
        if agent:
            self.db.host_agents.mark_disconnected(agent.id)
            self.db.host_events.record(host_id, "agent_disconnected")

    def record_event(self, host_id: int, event_type: str, payload_json: str | None = None) -> None:
        """Универсальный приёмник статусов агента — любой ``event_type`` (heartbeat,
        online, что угодно добавится позже) просто журналируется в host_events.
        Новый тип события НЕ требует изменений в этом сервисе или в WS-хендлере —
        расширяемость по типу, не по коду."""
        agent = self.db.host_agents.by_host(host_id)
        if agent:
            self.db.host_agents.touch(agent.id, status="connected")
            self.db.host_events.record(host_id, event_type, payload_json=payload_json)
