from aiohttp import web

from server.tools import _ok, _ctx, _safe_int

async def api_system_logs(request: web.Request) -> web.Response:
    """Журнал внутренних процессов сервера («История» → «Логи»): попытки
    автоустановки агента и т.п."""
    limit = _safe_int(request.query.get("limit"), 200)
    return _ok(_ctx(request).db.system_logs.recent(limit=limit))
