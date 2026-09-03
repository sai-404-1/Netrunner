from __future__ import annotations

from .domens.telegram import _telegram_poller
from .domens.update import _update_monitor

"""Async server server for NetRunner.

This module replaces the previous single-threaded http.server implementation
with an aiohttp-based async server. Long-running operations (task execution,
host checks, scheduler ticks) are dispatched as background asyncio tasks so the
HTTP API stays responsive.

Start the server from the project root:

    python -m web_main

or with custom options:

    python -m web_main --host 0.0.0.0 --port 8000 --db data/netrunner.db

Public API additions:
    POST /api/run                -> returns immediately {run_id, status}
    GET  /api/run/{id}/status    -> poll task status and per-host results
    WS   /ws                     -> receive task status updates
"""

import asyncio
import webbrowser
from aiohttp import web

from database import open_database
from services import HostService
from services.agent_service import AgentService
from .endpoints.build_app import build_app
from services.logger import Logger

logger = Logger()

# Размер батча fallback-пинга: SSH-пингуются только хосты БЕЗ endpoint-агента,
# по N машин за раз с паузой между батчами — не молотить всем списком разом.
PING_BATCH_SIZE = 10
PING_BATCH_PAUSE_SEC = 5

# TODO пересмотреть надобность, поскольку присутствует WebSocket
async def _periodic_ping(app: web.Application, interval: int):
    """Fallback-пинг по таймеру.

    SSH-пингуются ТОЛЬКО хосты без endpoint-агента: машины, где агент жив,
    сами поддерживают свой онлайн-статус через WS (online/heartbeat →
    AgentService.record_event). Запускается редко (см. ping_interval),
    машины идут батчами по PING_BATCH_SIZE с паузой между батчами.
    """
    db_path = app["ctx"].db_path
    while True:
        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            break
        try:
            db = open_database(db_path)
            try:
                host_service = HostService(db)
                agent_svc = AgentService(db)
                agented = agent_svc.agent_host_ids()
                targets = [h for h in host_service.all_hosts() if h.id not in agented]
                if not targets:
                    continue
                logger.info(
                    "Fallback-пинг: %d хост(ов) без агента, батчами по %d",
                    len(targets), PING_BATCH_SIZE,
                )
                for i in range(0, len(targets), PING_BATCH_SIZE):
                    batch = targets[i:i + PING_BATCH_SIZE]
                    await asyncio.gather(
                        *[host_service.check_host_async(h.id) for h in batch],
                        return_exceptions=True,
                    )
                    if i + PING_BATCH_SIZE < len(targets):
                        await asyncio.sleep(PING_BATCH_PAUSE_SEC)
            finally:
                db.close()
        except Exception as _ping_exc:
            logger.warning("Periodic host ping failed: %s", _ping_exc)


async def _agent_offline_sweeper(app: web.Application, interval: int = 60):
    """Offline-свип: раз в минуту помечает is_active=0 у хостов, чей агент
    молчит дольше порога (3 пропущенных heartbeat). Только SQL, без SSH —
    стоимость около нуля даже при сотнях хостов."""
    db_path = app["ctx"].db_path
    while True:
        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            break
        try:
            db = open_database(db_path)
            try:
                switched = AgentService(db).mark_stale_agents_offline()
                if switched:
                    logger.info("Offline-свип: %d хост(ов) помечены офлайн (агент молчит)", switched)
            finally:
                db.close()
        except Exception as _sweep_exc:
            logger.warning("Agent offline sweep failed: %s", _sweep_exc)


def run_web_server(
        app_context,
        host: str = "127.0.0.1",
        port: int = 8000,
        open_browser: bool = False,
        ping_interval: int = 1200,
) -> None:
    """Запускает локальную async server-панель NetRunner.

    ping_interval — интервал fallback-пинга хостов без агента (сек, по
    умолчанию 20 минут); 0 отключает fallback-пинг совсем.
    """

    app = build_app(app_context)

    async def _on_startup(_app):
        _app["auth_service"].create_default_user()
        if ping_interval > 0:
            ping_task = asyncio.create_task(_periodic_ping(_app, ping_interval))
            _app["ping_task"] = ping_task
        sweep_task = asyncio.create_task(_agent_offline_sweeper(_app))
        _app["offline_sweep_task"] = sweep_task
        _app["update_task"] = asyncio.create_task(_update_monitor(_app))
        _app["telegram_task"] = asyncio.create_task(_telegram_poller(_app))

    async def _on_cleanup(_app):
        for _key in ("ping_task", "offline_sweep_task", "update_task", "telegram_task"):
            if _key in _app:
                _app[_key].cancel()
                try:
                    await _app[_key]
                except asyncio.CancelledError:
                    pass
        for task in list(_app["background_tasks"]):
            task.cancel()
        await asyncio.gather(*_app["background_tasks"], return_exceptions=True)
        for ws in list(_app["websockets"]):
            await ws.close()

    app.on_startup.append(_on_startup)
    app.on_cleanup.append(_on_cleanup)

    url = f"http://{host}:{port}/"
    print(f"NetRunner server-GUI запущен: {url}")
    print("Для остановки нажмите Ctrl+C")

    if open_browser:
        webbrowser.open(url)

    web.run_app(app, host=host, port=port)
