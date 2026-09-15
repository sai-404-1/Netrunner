from aiohttp import web

from server.tools import _ok, _ctx, _safe_int, _error, is_teacher, allowed_host_ids


def _parse_sources(request: web.Request) -> list[str] | None:
    """Параметр ?sources=scenario,task — список source-слагай для фильтра."""
    raw = request.query.get("sources")
    if not raw:
        return None
    return [s.strip() for s in raw.split(",") if s.strip()]


def _entry_host_ids(entry_dict: dict) -> set[int]:
    """Хосты, которых касалась запись истории: host_id и/или payload['host_ids']."""
    ids: set[int] = set()
    hid = entry_dict.get("host_id")
    if hid is not None:
        ids.add(int(hid))
    for h in (entry_dict.get("payload") or {}).get("host_ids") or []:
        try:
            ids.add(int(h))
        except (TypeError, ValueError):
            pass
    return ids


async def api_history_entries(request: web.Request) -> web.Response:
    """Единая лента «История»: сервисные события NetRunner (history_entries).

    Поддерживает фильтр по сервисам и пагинацию:
    /api/history?limit=50&offset=100&sources=scenario,task
    Отдаёт {items: [...], total: N} — total для пагинации.

    Преподаватель видит только записи, касающиеся его кабинетов (по host_ids);
    записи без привязки к компьютерам ему не показываются.
    """
    limit = _safe_int(request.query.get("limit"), 50)
    offset = _safe_int(request.query.get("offset"), 0)
    sources = _parse_sources(request)
    ctx = _ctx(request)
    user = request.get("auth_user")

    if is_teacher(user):
        visible = allowed_host_ids(ctx.db, user)
        if not visible:
            return _ok({"items": [], "total": 0})
        # Берём весь срез по источникам и фильтруем по кабинетам в Python
        # (host_ids лежат в payload_json, SQL-фильтр по ним неудобен), затем
        # применяем пагинацию к уже отфильтрованному списку.
        all_entries = (ctx.history.to_dict(e) for e in ctx.history.list(limit=100000, sources=sources, offset=0))
        filtered = [d for d in all_entries if _entry_host_ids(d) & visible]
        total = len(filtered)
        items = filtered[offset:offset + limit]
        return _ok({"items": items, "total": total})

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
    entry_dict = ctx.history.to_dict(entry)
    user = request.get("auth_user")
    if is_teacher(user):
        visible = allowed_host_ids(ctx.db, user)
        if not visible or not (_entry_host_ids(entry_dict) & visible):
            return _error("Нет доступа к этой записи", status=403)
    return _ok(entry_dict)


async def api_history_types(request: web.Request) -> web.Response:
    """Реестр сервисов: slug, name, level, columns, event_types.

    Фронт строит фильтр-кнопки и колонки динамически — сервис, добавленный
    на сервере, появляется на фронте без пересборки.
    """
    return _ok(_ctx(request).history.registry_payload())
