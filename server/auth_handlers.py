from __future__ import annotations

import asyncio
import json
from typing import Any

from aiohttp import web

from database import open_database
from services.telegram_service import TelegramService


def _mask_telegram(username: str | None) -> str:
    """«ivan» → «i••n» — подсказка, куда ушёл код, без раскрытия аккаунта."""
    if not username:
        return "Telegram"
    if len(username) <= 2:
        return username[0] + "•"
    return f"{username[0]}{'•' * (len(username) - 2)}{username[-1]}"


def _send_login_code(db_path, chat_id, code: str) -> None:
    """Шлёт одноразовый код входа в Telegram (в отдельном потоке, своё соединение)."""
    db = open_database(db_path)
    try:
        TelegramService(db).send_message(
            chat_id,
            f"🔐 Код для входа в NetRunner: {code}\n"
            f"Код действует 5 минут. Если это были не вы — проигнорируйте сообщение "
            f"и смените пароль.",
        )
    finally:
        db.close()


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
    device_id = str(payload.get("device_id") or "").strip() or None
    result = auth.login(
        username=str(payload.get("username") or "").strip(),
        password=str(payload.get("password") or ""),
        device_id=device_id,
    )
    if not result.get("ok"):
        return _json_response(result, status=401)

    if result.get("mfa_required"):
        # Отправляем одноразовый код в Telegram; приватные поля не отдаём клиенту.
        chat_id = result.pop("_chat_id", None)
        code = result.pop("_code", None)
        tg_username = result.pop("_telegram_username", None)
        if chat_id and code:
            try:
                await asyncio.to_thread(_send_login_code, _ctx(request).db_path, chat_id, code)
            except Exception:  # noqa: BLE001 — не палим детали, но вход не должен падать
                return _json_response(
                    {"ok": False, "error": "Не удалось отправить код в Telegram. Попробуйте позже."},
                    status=502,
                )
        result["telegram_hint"] = _mask_telegram(tg_username)
        return _json_response(result)

    return _json_response(result)


async def api_login_verify(request: web.Request) -> web.Response:
    """Второй шаг входа: проверка одноразового кода из Telegram (step-up 2FA)."""
    payload = await _read_json(request)
    auth = _auth_service(request)
    device_id = (
        str(payload.get("device_id") or "").strip()
        or request.cookies.get("netrunner_device")
        or None
    )
    result = auth.verify_challenge(
        challenge_id=str(payload.get("challenge_id") or ""),
        code=str(payload.get("code") or "").strip(),
        device_id=device_id,
        trust=bool(payload.get("trust")),
        trust_label=str(payload.get("label") or "").strip() or None,
    )
    return _json_response(result, status=200 if result.get("ok") else 400)


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


async def api_me_update(request: web.Request) -> web.Response:
    """Самообслуживание профиля: смена своего имени и/или пароля."""
    user = request.get("auth_user")
    if not user:
        return _json_response({"ok": False, "error": "not authenticated"}, status=401)
    payload = await _read_json(request)
    result = _auth_service(request).update_profile(
        user_id=user.get("id"),
        new_username=str(payload.get("username") or "").strip() or None,
        current_password=payload.get("current_password") or None,
        new_password=payload.get("new_password") or None,
    )
    return _json_response(result, status=200 if result.get("ok") else 400)
