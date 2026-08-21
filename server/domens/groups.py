from aiohttp import web

from server.tools import _ctx, _ok, model_to_dict, _read_json, _error, _safe_int


async def api_groups(request: web.Request) -> web.Response:
    db = _ctx(request).db
    groups = []
    for group in db.groups.all():
        item = model_to_dict(group)
        item["hosts"] = db.groups.hosts(group.id)
        groups.append(item)
    return _ok(groups)


async def api_groups_create(request: web.Request) -> web.Response:
    import sqlite3 as _sqlite3
    ctx = _ctx(request)
    payload = await _read_json(request)
    name = str(payload.get("name") or "").strip()
    if not name:
        return _error("Название группы не может быть пустым")
    try:
        group = ctx.host_service.create_group(
            name=name,
            kind=str(payload.get("kind") or "custom").strip() or "custom",
            description=str(payload.get("description") or "").strip() or None,
        )
    except _sqlite3.IntegrityError:
        return _error(f"Группа с названием «{name}» уже существует")
    return _ok(group)


async def api_groups_update(request: web.Request) -> web.Response:
    ctx = _ctx(request)
    payload = await _read_json(request)
    group_id = _safe_int(payload.get("id"))
    updates = {k: v for k, v in payload.items() if k != "id" and v is not None}
    group = ctx.db.groups.update(group_id, **updates)
    return _ok(group)


async def api_groups_delete(request: web.Request) -> web.Response:
    ctx = _ctx(request)
    payload = await _read_json(request)
    group_id = _safe_int(payload.get("id"))
    ctx.db.groups.delete(group_id)
    return _ok({"deleted": group_id})


async def api_groups_add_host(request: web.Request) -> web.Response:
    ctx = _ctx(request)
    payload = await _read_json(request)
    link = ctx.host_service.add_host_to_group(
        group_id=_safe_int(payload.get("group_id")),
        host_id=_safe_int(payload.get("host_id")),
    )
    return _ok(link)