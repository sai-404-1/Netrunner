import json
from typing import Any
from dataclasses import asdict, is_dataclass

from aiohttp import web

def model_to_dict(value: Any) -> Any:
    """Преобразует dataclass-модели, списки и словари в JSON-совместимый вид."""

    if value is None:
        return None
    if is_dataclass(value):
        data = asdict(value)
        # Никогда не отдаём зашифрованный пароль хоста наружу.
        data.pop("password_encrypted", None)
        return data
    if isinstance(value, list):
        return [model_to_dict(item) for item in value]
    if isinstance(value, tuple):
        return [model_to_dict(item) for item in value]
    if isinstance(value, dict):
        return {key: model_to_dict(item) for key, item in value.items()}
    return value


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _ok(data: Any) -> web.Response:
    return _json_response({"ok": True, "data": data})


def _error(message: str, status: int = 400) -> web.Response:
    return _json_response({"ok": False, "error": message}, status=status)


def _ctx(request: web.Request):
    return request.app["ctx"]

def _json_response(data: Any, status: int = 200) -> web.Response:
    body = json.dumps(model_to_dict(data), ensure_ascii=False, default=str).encode("utf-8")
    return web.Response(
        body=body,
        status=status,
        content_type="application/json",
        charset="utf-8",
    )

async def _read_json(request: web.Request) -> dict[str, Any]:
    try:
        data = await request.json()
    except Exception as exc:
        raise web.HTTPBadRequest(
            body=json.dumps({"ok": False, "error": f"Invalid JSON: {exc}"}, ensure_ascii=False)
        )
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise web.HTTPBadRequest(
            body=json.dumps({"ok": False, "error": "JSON payload must be an object"}, ensure_ascii=False)
        )
    return data

def _require_admin(request: web.Request) -> bool:
    user = request.get("auth_user")
    return bool(user and user.get("is_superuser"))


def allowed_group_ids(db, user) -> set[int] | None:
    """Множество id кабинетов, доступных пользователю, или None без ограничений.

    - суперпользователь → None (видит всё);
    - преподаватель → строго только явно выданные кабинеты (пусто → пустое
      множество, то есть не видит ничего, пока доступ не выдан);
    - прочие не-суперпользователи → исторически: если кабинеты не выданы,
      ограничений нет (None), иначе только выданные.
    """
    if not user or user.get("is_superuser"):
        return None
    access_rows = db.user_group_access.by_user(int(user["id"]))
    role = user.get("role") or "user"
    if role == "teacher":
        return {row.group_id for row in access_rows}
    if not access_rows:
        return None
    return {row.group_id for row in access_rows}


def allowed_host_ids(db, user) -> set[int] | None:
    """Множество id хостов из доступных пользователю кабинетов, или None без
    ограничений. Строится поверх :func:`allowed_group_ids`."""
    group_ids = allowed_group_ids(db, user)
    if group_ids is None:
        return None
    host_ids: set[int] = set()
    for gid in group_ids:
        for h in db.groups.hosts(gid):
            host_ids.add(h.id)
    return host_ids


def is_teacher(user) -> bool:
    """Роль «преподаватель» (не суперпользователь)."""
    return bool(user) and (user.get("role") == "teacher") and not user.get("is_superuser")


def host_visible(db, user, host_id: int) -> bool:
    """Доступен ли конкретный хост пользователю (см. :func:`allowed_host_ids`)."""
    host_ids = allowed_host_ids(db, user)
    return host_ids is None or host_id in host_ids