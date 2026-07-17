#!/usr/bin/env python3
"""NetRunner endpoint-агент — report-only, минимум действий.

Сам открывает исходящее WebSocket-соединение к серверу NetRunner (звонит домой):
работает через NAT, на хосте не нужно открывать порты, сервер не подключается
внутрь. НЕ принимает и не выполняет никаких команд с сервера — читает входящие
сообщения только чтобы вовремя заметить закрытие соединения, содержимое никогда
не интерпретируется как команда. Это осознанное ограничение blast radius: даже
если сервер NetRunner скомпрометирован, агент не даёт атакующему канал для
выполнения кода на хосте.

С хоста на сервер уходят ТОЛЬКО статусы — никогда команды на исполнение:
- "online" — один раз сразу после установления соединения (агент стартует по
  systemd при загрузке, так что первый "online" == "компьютер включился");
- "heartbeat" — периодически, пока соединение живо (hostname/uptime/время).

Расширяемость на будущее: send_status() — это общая точка выхода для отправки
статуса произвольного типа. Новый вид события добавляется вызовом
``await send_status(ws, "какой-то_тип", поле=значение)`` в нужном месте кода
(например, в отдельном хуке ExecStopPost для события выключения) — протокол и
серверная сторона (services/agent_service.py::record_event) уже готовы принять
любой ``type`` без изменений.

Конфиг — /etc/netrunner-agent/config.json (host_id, token, server_ws_url),
пишется модулем computer/module/agent_provision.py при установке.

Зависимость: пакет `websockets` (pip install websockets). Сознательно не
реализована ручная WebSocket-фреймовка — это единственная внешняя зависимость
агента, устанавливается один раз при провижининге (см. agent/README.md).
"""

from __future__ import annotations

import asyncio
import json
import logging
import platform
import socket
import sys
import time
from pathlib import Path
from typing import Any

CONFIG_PATH = Path("/etc/netrunner-agent/config.json")
HEARTBEAT_INTERVAL_SEC = 60
RECONNECT_DELAY_SEC = 15

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s netrunner-agent %(levelname)s %(message)s",
)
log = logging.getLogger("netrunner-agent")


def load_config() -> dict:
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    for key in ("host_id", "token", "server_ws_url"):
        if not data.get(key):
            raise ValueError(f"Config {CONFIG_PATH} missing required key: {key}")
    return data


def _uptime_seconds() -> float | None:
    try:
        with open("/proc/uptime") as f:
            return float(f.read().split()[0])
    except Exception:  # noqa: BLE001 — телеметрия best-effort, не критична
        return None


async def send_status(ws, status_type: str, **fields: Any) -> None:
    """Единая точка отправки любого статуса агента. Конверт сообщения одинаков
    для всех типов — {"type", "hostname", "ts", ...остальные поля}, поэтому
    добавление нового типа статуса не требует менять протокол, только вызвать
    эту функцию с новым status_type в нужном месте."""
    payload = {
        "type": status_type,
        "hostname": socket.gethostname(),
        "ts": time.time(),
        **fields,
    }
    await ws.send(json.dumps(payload))


async def run_forever(config: dict) -> None:
    try:
        import websockets
    except ImportError:
        log.error(
            "Пакет 'websockets' не установлен (pip install websockets) — агент не может подключиться."
        )
        sys.exit(1)

    hello = {"type": "hello", "host_id": config["host_id"], "token": config["token"]}

    while True:
        # asyncio.wait_for(...) вместо open_timeout= — переносимо между версиями
        # websockets (некоторые старые не принимают этот именованный аргумент).
        try:
            ws = await asyncio.wait_for(
                websockets.connect(config["server_ws_url"]), timeout=10
            )
        except Exception as exc:  # noqa: BLE001 — сеть нестабильна, просто переподключаемся
            log.warning("Не удалось подключиться (%s), повтор через %ss", exc, RECONNECT_DELAY_SEC)
            await asyncio.sleep(RECONNECT_DELAY_SEC)
            continue

        try:
            await ws.send(json.dumps(hello))
            log.info("Подключено к %s", config["server_ws_url"])

            # Первое сообщение после успешного коннекта — "online". Агент стартует
            # через systemd при загрузке хоста, поэтому для сервера это и есть
            # сигнал "компьютер включился".
            await send_status(ws, "online", platform=platform.platform())

            while True:
                await send_status(ws, "heartbeat", uptime_seconds=_uptime_seconds())
                try:
                    # Report-only: любое входящее сообщение от сервера игнорируется —
                    # агент никогда не интерпретирует его как команду. Читаем только
                    # чтобы вовремя заметить закрытие соединения (short timeout).
                    await asyncio.wait_for(ws.recv(), timeout=HEARTBEAT_INTERVAL_SEC)
                except asyncio.TimeoutError:
                    pass
        except Exception as exc:  # noqa: BLE001
            log.warning("Соединение потеряно (%s), повтор через %ss", exc, RECONNECT_DELAY_SEC)
        finally:
            try:
                await ws.close()
            except Exception:  # noqa: BLE001
                pass
        await asyncio.sleep(RECONNECT_DELAY_SEC)


def main() -> None:
    config = load_config()
    asyncio.run(run_forever(config))


if __name__ == "__main__":
    main()
