import asyncio

from aiohttp import web

from database import open_database
from server.tools import _error, _ctx, _ok, _require_admin, _read_json
from services.telegram_service import TelegramService

from services.logger import Logger

logger = Logger()

def _auth_uid(request: web.Request) -> int | None:
    user = request.get("auth_user")
    if not user or int(user.get("id", 0)) <= 0:
        return None
    return int(user["id"])


async def api_me_telegram_status(request: web.Request) -> web.Response:
    uid = _auth_uid(request)
    if uid is None:
        return _error("not authenticated", status=401)
    db = _ctx(request).db
    row = db.users.get(uid)
    return _ok(TelegramService(db).status(row))


async def api_me_telegram_link(request: web.Request) -> web.Response:
    uid = _auth_uid(request)
    if uid is None:
        return _error("not authenticated", status=401)

    def _work(db_path):
        db = open_database(db_path)
        try:
            row = db.users.get(uid)
            return TelegramService(db).create_link_code(row)
        finally:
            db.close()

    res = await asyncio.to_thread(_work, _ctx(request).db_path)
    return _ok(res) if res.get("ok") else _error(res.get("error", "Ошибка"), status=400)


async def api_me_telegram_unlink(request: web.Request) -> web.Response:
    uid = _auth_uid(request)
    if uid is None:
        return _error("not authenticated", status=401)
    TelegramService(_ctx(request).db).unlink(uid)
    return _ok({"unlinked": True})


async def api_admin_telegram_get(request: web.Request) -> web.Response:
    if not _require_admin(request):
        return _error("Только для администратора", status=403)
    svc = TelegramService(_ctx(request).db)
    return _ok({
        "configured": svc.configured(),
        "bot_username": _ctx(request).db.app_settings.get("telegram_bot_username"),
    })


async def api_admin_telegram_set(request: web.Request) -> web.Response:
    if not _require_admin(request):
        return _error("Только для администратора", status=403)
    payload = await _read_json(request)
    # пусто/нет ключа — не менять; '-' — очистить; иначе установить новый токен.
    raw = payload.get("token")
    action = None
    if isinstance(raw, str):
        s = raw.strip()
        if s == "-":
            action = ("clear", None)
        elif s:
            action = ("set", s)

    def _work(db_path, action: object):
        db = open_database(db_path)
        try:
            svc = TelegramService(db)
            if action:
                svc.set_token(None if action[0] == "clear" else action[1])
            bot = svc.get_bot_username() if svc.configured() else None  # валидируем токен через getMe
            return {"configured": svc.configured(), "bot_username": bot}
        finally:
            db.close()

    res = await asyncio.to_thread(_work, _ctx(request).db_path, action)
    return _ok(res)


# TODO пересмотреть надобность
async def _telegram_poller(app: web.Application):
    """Фоновый поллер Telegram: ловит `/start <code>` и привязывает аккаунты.

    Сетевые вызовы и БД — в отдельном потоке со своим соединением (sqlite не
    потокобезопасен). Если бот не настроен — опрашиваем реже.
    """
    db_path = app["ctx"].db_path

    def _work():
        db = open_database(db_path)
        try:
            svc = TelegramService(db)
            if not svc.configured():
                return False
            svc.poll_once()
            return True
        finally:
            db.close()

    while True:
        configured = False
        try:
            configured = await asyncio.to_thread(_work)
        except asyncio.CancelledError:
            break
        except Exception as exc:  # noqa: BLE001
            logger.warning("Telegram poller failed: %s", exc)
        try:
            await asyncio.sleep(3 if configured else 30)
        except asyncio.CancelledError:
            break