from aiohttp import web

from server.tools import _ok, _ctx, _safe_int, _error


def _parse_sources(request: web.Request) -> list[str] | None:
    """Параметр ?sources=scenario,task — список source-слагай для фильтра."""
    raw = request.query.get("sources")
    if not raw:
        return None
    return [s.strip() for s in raw.split(",") if s.strip()]


async def api_history_entries(request: web.Request) -> web.Response:
    """Единая лента «История»: сервисные события NetRunner (history_entries).

    Поддерживает фильтр по сервисам и пагинацию:
    /api/history?limit=50&offset=100&sources=scenario,task
    Отдаёт {items: [...], total: N} — total для пагинации.
    """
    limit = _safe_int(request.query.get("limit"), 50)
    offset = _safe_int(request.query.get("offset"), 0)
    sources = _parse_sources(request)
    ctx = _ctx(request)
    items = [ctx.history.to_dict(e) for e in ctx.history.list(limit=limit, sources=sources, offset=offset)]
    total = ctx.history.count(sources=sources)
    return _ok({"items": items, "total": total})


async def api_history_entry(request: web.Request) -> web.Response:
    """Подробности конкретной записи истории (лениво, по id)."""
    ctx = _ctx(request)
    entry_id = _safe_int(request.match_info.get("entry_id"), 0)
    entry = ctx.history.get_entry(entry_id)
    if entry is None:
        return _error("Запись не найдена", status=404)
    return _ok(ctx.history.to_dict(entry))


async def api_history_types(request: web.Request) -> web.Response:
    """Реестр сервисов: slug, name, level, columns, event_types.

    Фронт строит фильтр-кнопки и колонки динамически — сервис, добавленный
    на сервере, появляется на фронте без пересборки.
    """
    return _ok(_ctx(request).history.registry_payload())
