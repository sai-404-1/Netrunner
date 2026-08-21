from aiohttp import web

from server.domens.telegram import _auth_uid
from server.tools import _error, _ok, _read_json

# Функции работали в связке с телеграмом
# Код сохранён для использования в будущем
# Код не тестировался корректно

async def api_me_devices_list(request: web.Request) -> web.Response:
    uid = _auth_uid(request)
    if uid is None:
        return _error("not authenticated", status=401)
    current = request.cookies.get("netrunner_device")
    devices = request.app["auth_service"].list_trusted_devices(uid, current_device_id=current)
    return _ok({"devices": devices})


async def api_me_devices_trust(request: web.Request) -> web.Response:
    """Сменить срок доверия устройству (напр. «навсегда» из кабинета)."""
    uid = _auth_uid(request)
    if uid is None:
        return _error("not authenticated", status=401)
    payload = await _read_json(request)
    device_id = str(payload.get("device_id") or "").strip() or request.cookies.get("netrunner_device")
    if not device_id:
        return _error("device_id обязателен", status=400)
    res = request.app["auth_service"].set_device_trust(
        uid, device_id,
        forever=bool(payload.get("forever")),
        label=str(payload.get("label") or "").strip() or None,
    )
    return _ok(res) if res.get("ok") else _error(res.get("error", "Ошибка"), status=400)


async def api_me_devices_revoke(request: web.Request) -> web.Response:
    uid = _auth_uid(request)
    if uid is None:
        return _error("not authenticated", status=401)
    payload = await _read_json(request)
    device_id = str(payload.get("device_id") or "").strip()
    if not device_id:
        return _error("device_id обязателен", status=400)
    res = request.app["auth_service"].revoke_device(uid, device_id)
    return _ok({"revoked": res.get("ok", False)})