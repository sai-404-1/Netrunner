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
соединения при невалидном токене (см. agent_websocket_handler в server/server.py).
"""

from __future__ import annotations

import secrets

from aiohttp import web
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from database.repos.base import utcnow_iso
from database.models.host_agent import HostAgent
from server.domens.websocket import _default_agent_ws_url
from services.secrets import decrypt_secret, encrypt_secret

from .logger import Logger

logger = Logger()

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

    def get_existing(self, db, host_id: int) -> HostAgent | None:
        """Возвращает запись агента хоста (для переустановки без ротации ключа)."""
        return db.host_agents.by_host(host_id)

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
            # Агент установил WS-соединение = хост в сети. Обновляем статус хоста
            # сразу, без SSH-пинга (агент сам докладывает о себе).
            self.db.hosts.update(host_id, is_active=1, last_seen_at=utcnow_iso())

    def record_disconnect(self, host_id: int) -> None:
        agent = self.db.host_agents.by_host(host_id)
        if agent:
            self.db.host_agents.mark_disconnected(agent.id)
            self.db.host_events.record(host_id, "agent_disconnected")
            # НЕ трогаем hosts.is_active здесь: WS мог упасть при живом хосте.
            # Offline-статус решает фоновый свип по протухшему last_seen_at.

    def record_event(self, host_id: int, event_type: str, payload_json: str | None = None) -> None:
        """Универсальный приёмник статусов агента — любой ``event_type`` (heartbeat,
        online, что угодно добавится позже) просто журналируется в host_events.
        Новый тип события НЕ требует изменений в этом сервисе или в WS-хендлере —
        расширяемость по типу, не по коду."""
        agent = self.db.host_agents.by_host(host_id)
        if agent:
            self.db.host_agents.touch(agent.id, status="connected")
            self.db.host_events.record(host_id, event_type, payload_json=payload_json)
            # online/heartbeat = хост жив. Обновляем статус хоста без SSH-пинга.
            if event_type in ("online", "heartbeat"):
                self.db.hosts.update(host_id, is_active=1, last_seen_at=utcnow_iso())

    # Порог актуальности heartbeat агента: 180с = 3 пропущенных heartbeat
    # (агент шлёт heartbeat каждые 60с). После этого хост считается офлайн.
    AGENT_HEARTBEAT_STALE_SEC = 180

    def agent_host_ids(self) -> set[int]:
        """ID хостов, у которых ЕСТЬ запись endpoint-агента. Такие хосты
        SSH-пинговать не нужно: их статус поддерживают online/heartbeat агента."""
        return {a.host_id for a in self.db.host_agents.all()}

    def mark_stale_agents_offline(self) -> int:
        """Offline-свип: хосты с агентом, от которого нет heartbeat дольше
        AGENT_HEARTBEAT_STALE_SEC, помечаются is_active=0. Возвращает число
        переключённых хостов. Только SQL, без SSH — стоимость около нуля."""
        from datetime import datetime, timedelta, timezone

        threshold = (datetime.now(timezone.utc) - timedelta(seconds=self.AGENT_HEARTBEAT_STALE_SEC)).isoformat()
        switched = 0
        for agent in self.db.host_agents.all():
            seen = agent.last_seen_at
            # Без last_seen (агент ставился, но ни разу не подключался) — не трогаем:
            # статус хоста определяет SSH-пинг, как для agentless-хоста.
            if not seen or seen >= threshold:
                continue
            host = self.db.hosts.get(agent.host_id)
            if host is not None and host.is_active:
                self.db.hosts.update(agent.host_id, is_active=0)
                switched += 1
        return switched


async def _auto_install_agent(app: web.Application, host) -> None:
    """Фоновая попытка установки endpoint-агента сразу после добавления хоста.
    Не блокирует создание хоста и не считается ошибкой добавления — при неудаче
    (например, нет passwordless sudo) просто пишется запись в системные логи
    («История» → «Логи»), которую видно в UI."""
    ctx = app["ctx"]
    from computer.module.agent_provision import CustomModule as agentProvisionModule
    from services.task_runner import ModuleContext

    module_ctx = ModuleContext(
        logger=logger, task_run_id=0, to_computer=ctx.host_service.to_computer, db=ctx.db,
        host_service=ctx.host_service,
    )
    server_ws_url = _default_agent_ws_url()
    try:
        result = await agentProvisionModule.run_for_host(module_ctx, host, server_ws_url=server_ws_url)
    except Exception as exc:  # noqa: BLE001 — фон: любая ошибка = запись в лог, не падение сервера
        logger.warning("Auto agent install failed for host_id=%s: %s", host.id, exc)
        ctx.db.system_logs.record(
            "agent_install", "error", f"Хост «{host.name}»: {exc}", host_id=host.id,
        )
        if hasattr(ctx, "history"):
            ctx.history.record(
                source="agent",
                event_type="agent_install",
                title=f"Ошибка установки агента на хост «{host.name}»",
                description=str(exc),
                payload={"host_name": host.name, "action": "install"},
                host_id=host.id,
                level="error",
            )
        return

    level = "error" if result.get("status") == "error" else "success"
    output = str(result.get("output") or "")[:4000]
    ctx.db.system_logs.record(
        "agent_install", level, f"Хост «{host.name}» ({server_ws_url}): {output}", host_id=host.id,
    )
    if hasattr(ctx, "history"):
        ctx.history.record(
            source="agent",
            event_type="agent_install",
            title=f"Агент установлен на хост «{host.name}»" if level == "success" else f"Ошибка установки агента на хост «{host.name}»",
            description=output,
            payload={"host_name": host.name, "action": "install"},
            host_id=host.id,
            level=level,
        )