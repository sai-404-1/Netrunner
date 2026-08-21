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