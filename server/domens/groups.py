from aiohttp import web

from server.tools import _ctx, _ok, model_to_dict, _read_json, _error, _safe_int, allowed_group_ids, is_teacher


def _deny_teacher(request: web.Request):
    """403, если запрос от преподавателя: управление кабинетами — админское."""
    if is_teacher(request.get("auth_user")):
        return _error("Управление кабинетами доступно только администратору", status=403)
    return None


async def api_groups(request: web.Request) -> web.Response:
    db = _ctx(request).db
    group_ids = allowed_group_ids(db, request.get("auth_user"))
    groups = []
    for group in db.groups.all():
        if group_ids is not None and group.id not in group_ids:
            continue
        item = model_to_dict(group)
        item["hosts"] = db.groups.hosts(group.id)
        groups.append(item)
    return _ok(groups)


async def api_groups_create(request: web.Request) -> web.Response:
    import sqlite3 as _sqlite3
    denied = _deny_teacher(request)
    if denied:
        return denied
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
    denied = _deny_teacher(request)
    if denied:
        return denied
    ctx = _ctx(request)
    payload = await _read_json(request)
    group_id = _safe_int(payload.get("id"))
    updates = {k: v for k, v in payload.items() if k != "id" and v is not None}
    group = ctx.db.groups.update(group_id, **updates)
    return _ok(group)


async def api_groups_delete(request: web.Request) -> web.Response:
    denied = _deny_teacher(request)
    if denied:
        return denied
    ctx = _ctx(request)
    payload = await _read_json(request)
    group_id = _safe_int(payload.get("id"))
    ctx.db.groups.delete(group_id)
    return _ok({"deleted": group_id})


async def api_groups_add_host(request: web.Request) -> web.Response:
    denied = _deny_teacher(request)
    if denied:
        return denied
    ctx = _ctx(request)
    payload = await _read_json(request)
    link = ctx.host_service.add_host_to_group(
        group_id=_safe_int(payload.get("group_id")),
        host_id=_safe_int(payload.get("host_id")),
    )
    return _ok(link)