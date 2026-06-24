from __future__ import annotations

import json
from typing import Any

from aiohttp import web


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


def _ctx(request: web.Request):
    return request.app["ctx"]


def _db(request: web.Request):
    return request.app["ctx"].db


def _auth_service(request: web.Request):
    return request.app["auth_service"]


def _json_response(data: Any, status: int = 200) -> web.Response:
    body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
    return web.Response(
        body=body,
        status=status,
        content_type="application/json",
        charset="utf-8",
    )


async def api_register(request: web.Request) -> web.Response:
    db = _db(request)
    if db.users.all():
        auth = _auth_service(request)
        token = ""
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        if not token:
            token = request.query.get("token", "")
        if not token:
            token = request.cookies.get("netrunner_token", "")
        caller = auth.me(token)
        if not caller or not caller.get("is_superuser"):
            return _json_response(
                {"ok": False, "error": "Registration is closed. Contact an administrator."},
                status=403,
            )
    payload = await _read_json(request)
    auth = _auth_service(request)
    result = auth.register(
        username=str(payload.get("username") or "").strip(),
        password=str(payload.get("password") or ""),
        email=str(payload.get("email") or "").strip() or None,
    )
    return _json_response(result, status=201 if result.get("ok") else 400)


async def api_login(request: web.Request) -> web.Response:
    payload = await _read_json(request)
    auth = _auth_service(request)
    result = auth.login(
        username=str(payload.get("username") or "").strip(),
        password=str(payload.get("password") or ""),
    )
    if not result.get("ok"):
        return _json_response(result, status=401)
    return _json_response(result)


async def api_logout(request: web.Request) -> web.Response:
    user = request.get("auth_user")
    if user:
        _auth_service(request).logout(user["id"])
    return _json_response({"ok": True})


async def api_me(request: web.Request) -> web.Response:
    user = request.get("auth_user")
    if not user:
        return _json_response({"ok": False, "error": "not authenticated"}, status=401)
    return _json_response({"ok": True, "user": user})
