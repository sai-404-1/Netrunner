from aiohttp import web

from server.tools import _ctx, _ok, _read_json
from services.secrets import encrypt_secret


async def api_default_creds_get(request: web.Request) -> web.Response:
    """Стандартные креды для добавления хостов (host_default_credentials).

    Возвращает только username — зашифрованный пароль наружу не отдаётся
    (он используется сервером для автоподстановки при создании хоста).
    """
    db = _ctx(request).db
    defaults = db.host_default_cred.get_default() if hasattr(db, "host_default_cred") else None
    if defaults is None:
        return _ok({"username": "", "has_password": False})
    return _ok({
        "username": defaults.username or "",
        # Признак наличия пароля, чтобы фронт понимал, настроены ли креды
        # (сам пароль не отдаём).
        "has_password": bool(defaults.password_encrypted),
    })


async def api_default_creds_update(request: web.Request) -> web.Response:
    """Обновить стандартные креды (username, пароль зашифровываем).

    Оба поля опциональны: передай только те, что меняешь. Пустая строка в
    password удаляет сохранённый пароль.
    """
    ctx = _ctx(request)
    payload = await _read_json(request)
    db = ctx.db

    username = payload.get("username")
    password = payload.get("password")

    data = {}
    if username is not None:
        data["username"] = str(username).strip()
    if password is not None:
        p = str(password).strip()
        data["password_encrypted"] = encrypt_secret(p) if p else ""

    if not data:
        return _ok({"ok": True, "changed": False})

    existing = db.host_default_cred.get_default()
    if existing is None:
        # Таблицы с единственной строкой: если записи нет — создаём.
        db.host_default_cred.create(**data)
    else:
        db.host_default_cred.update(existing.id, **data)

    # Вернём актуальное состояние наружу (пароль не отдаём).
    updated = db.host_default_cred.get_default()
    return _ok({
        "username": updated.username or "",
        "has_password": bool(updated.password_encrypted),
        "changed": True,
    })
