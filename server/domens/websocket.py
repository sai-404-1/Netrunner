import json
from aiohttp import web

from server.tools import model_to_dict, _safe_int
from services.logger import Logger

logger = Logger()

async def websocket_handler(request: web.Request) -> web.WebSocketResponse:
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    request.app["websockets"].add(ws)
    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                except Exception:
                    continue
                action = data.get("action")
                if action == "subscribe":
                    run_id = _safe_int(data.get("run_id"))
                    run = request.app["ctx"].db.task_runs.get(run_id)
                    if run is not None:
                        await ws.send_str(
                            json.dumps({"type": "task_status", "run": model_to_dict(run)}, ensure_ascii=False,
                                       default=str)
                        )
    finally:
        request.app["websockets"].discard(ws)
    return ws


async def agent_websocket_handler(request: web.Request) -> web.WebSocketResponse:
    """Приём соединений endpoint-агентов — не путать с /ws (клиент веб-панели).
    Агент сам звонит сюда исходящим соединением; сервер никогда не инициирует
    запрос к агенту и не шлёт ему ничего, кроме закрытия соединения при невалидном
    токене — report-only в обе стороны. Любой присланный агентом тип сообщения
    (кроме служебного "hello") просто журналируется как есть — новый тип статуса
    не требует изменений здесь, см. AgentService.record_event."""
    from services.agent_service import AgentService

    ws = web.WebSocketResponse()
    await ws.prepare(request)
    ctx = request.app["ctx"]
    agent_svc = AgentService(ctx.db)
    host_id: int | None = None
    try:
        async for msg in ws:
            if msg.type != web.WSMsgType.TEXT:
                continue
            try:
                data = json.loads(msg.data)
            except json.JSONDecodeError:
                logger.warning("Received invalid JSON payload from agent")
                continue

            msg_type = data.get("type")

            if host_id is None:
                if msg_type != "hello":
                    await ws.close(code=4001, message=b"expected hello")
                    break
                candidate_id = _safe_int(data.get("host_id"))
                token = str(data.get("token") or "")
                if not candidate_id or not agent_svc.verify_token(candidate_id, token):
                    await ws.close(code=4003, message=b"invalid token")
                    break
                host_id = candidate_id
                agent_svc.record_connect(host_id)
                logger.info("Agent connected for host_id=%s", host_id)
                continue

            if msg_type:
                agent_svc.record_event(
                    host_id, msg_type, payload_json=json.dumps(data, ensure_ascii=False, default=str)
                )
                if hasattr(ctx, "history"):
                    ctx.history.record(
                        source="agent_message",
                        event_type="agent_msg",
                        title=f"Сообщение от агента: {msg_type}",
                        description=json.dumps(data, ensure_ascii=False, default=str)[:4000],
                        payload={"host_name": f"host-{host_id}", "message_type": msg_type},
                        host_id=host_id,
                        level="info",
                    )
    finally:
        if host_id is not None:
            agent_svc.record_disconnect(host_id)
            logger.info("Agent disconnected for host_id=%s", host_id)
    return ws


def _default_agent_ws_url() -> str:
    """Угадывает адрес сервера для конфига агента: LAN-IP этой машины + порт
    Next.js в Docker (3001) + префикс /api/python/, который проксируется на
    бэкенд. Эвристика для автоустановки при добавлении хоста — если она угадала
    неверно, администратор может перевыпустить агента вручную через модуль
    «Установка endpoint-агента» с явно указанным адресом."""
    import socket
    try:
        ip = socket.gethostbyname(socket.gethostname())
        logger.debug(f"Был применён IP для вебсокета: {ip}")
    except (socket.gaierror, OSError):
        ip = "127.0.0.1"
        logger.debug(f"Ошибка определения имени хоста (IP) для вебсокета: {ip}")
    return f"ws://{ip}:3001/api/python/agent/ws"


async def _broadcast_task_update(app: web.Application, run_id: int):
    """Push the latest task-run state to every connected WebSocket client."""
    run = app["ctx"].db.task_runs.get(run_id)
    if run is None:
        return
    message = json.dumps({"type": "task_status", "run": model_to_dict(run)}, ensure_ascii=False, default=str)
    dead = set()
    for ws in app["websockets"]:
        try:
            await ws.send_str(message)
        except Exception:
            dead.add(ws)
    app["websockets"].difference_update(dead)