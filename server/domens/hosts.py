from aiohttp import web
from server.tools import _ctx, _ok, model_to_dict, _read_json, _safe_int, _error
from services.agent_service import _auto_install_agent
from services.host_service import _provision_ssh_key, _run_background
from services.secrets import encrypt_secret, decrypt_secret


async def api_hosts(request: web.Request) -> web.Response:
    db = _ctx(request).db
    return _ok(_hosts_payload(db, request.get("auth_user")))


def _hosts_payload(db, user) -> list:
    """Общий сбор хостов для /api/hosts и /api/hosts/status."""
    all_hosts = db.hosts.all()
    if user and not user.get("is_superuser"):
        access_rows = db.user_group_access.by_user(int(user["id"]))
        if access_rows:
            allowed_group_ids = {row.group_id for row in access_rows}
            allowed_host_ids: set[int] = set()
            for gid in allowed_group_ids:
                for h in db.groups.hosts(gid):
                    allowed_host_ids.add(h.id)
            all_hosts = [h for h in all_hosts if h.id in allowed_host_ids]
    hosts = []
    for host in all_hosts:
        item = model_to_dict(host)
        item["last_seen"] = host.last_seen_at
        item["group_id"] = db.groups.first_group_id_for_host(host.id)
        group = db.groups.first_group_for_host(host.id)
        item["group_name"] = group.name if group else None
        hosts.append(item)
    return hosts


async def api_hosts_status(request: web.Request) -> web.Response:
    """Лёгкий статус всех хостов для живого опроса сетки (каждые 5с).

    Отдаёт только id/имя/адрес/активность — БЕЗ перепинга хостов, читает из базы.
    Фронт сам делит на «в сети» / «не в сети» и рисует анимацию.
    """
    db = _ctx(request).db
    rows = _hosts_payload(db, request.get("auth_user"))
    payload = [
        {
            "id": h.get("id"),
            "name": h.get("name"),
            "address": h.get("address"),
            "group_id": h.get("group_id"),
            "group_name": h.get("group_name"),
            "is_active": bool(h.get("is_active")),
            "last_seen": h.get("last_seen"),
        }
        for h in rows
    ]
    return _ok(payload)


async def api_hosts_create(request: web.Request) -> web.Response:
    ctx = _ctx(request)
    payload = await _read_json(request)
    ssh_key_id = payload.get("ssh_key_id")
    if ssh_key_id is not None:
        ssh_key_id = int(ssh_key_id) if ssh_key_id else None
    username = str(payload.get("username") or "").strip()
    address = str(payload.get("address") or "").strip()
    port = _safe_int(payload.get("port"), 22)
    password = str(payload.get("password") or "").strip() or None

    # Автозаполнение стандартных кредов (таблица host_default_credentials):
    # если пользователь НЕ ввёл свой username/пароль (поле не изменялось —
    # пришло пустым), сервер подставляет стандартные креды. Если же ввёл —
    # применяем то, что ввёл пользователь.
    defaults = ctx.db.host_default_cred.get_default() if hasattr(ctx.db, "host_default_cred") else None
    if not username and defaults is not None and defaults.username:
        username = defaults.username
    if not password and defaults is not None and defaults.password_encrypted:
        try:
            password = decrypt_secret(defaults.password_encrypted)
        except Exception:
            password = None

    if password:
        await _provision_ssh_key(ctx, username, address, port, password, ssh_key_id)
    host = ctx.host_service.add_host(
        name=str(payload.get("name") or "").strip(),
        address=address,
        username=username,
        port=port,
        ssh_key_id=ssh_key_id,
        description=str(payload.get("description") or "").strip() or None,
        password=password,
    )
    # Попытка установить endpoint-агента сразу при добавлении хоста — фоном, не
    # блокирует ответ и не считается ошибкой добавления хоста самого по себе.
    await _run_background(request.app, _auto_install_agent(request.app, host))
    return _ok(host)


async def api_hosts_update(request: web.Request) -> web.Response:
    ctx = _ctx(request)
    payload = await _read_json(request)
    host_id = _safe_int(payload.get("id"))
    password = None
    allowed = {}
    for k, v in payload.items():
        if k in ("id", "group_id"):
            continue
        if k == "password":
            password = str(v or "").strip() or None
            continue
        if k == "ssh_key_id":
            allowed[k] = int(v) if v else None
        elif v is not None:
            allowed[k] = v
    if password:
        host = ctx.db.hosts.get(host_id)
        if host:
            await _provision_ssh_key(
                ctx,
                host.username,
                host.address,
                host.port,
                password,
                allowed.get("ssh_key_id") or host.ssh_key_id,
            )
        # Сохраняем пароль (зашифрованным) для будущей перепривязки ключа.
        allowed["password_encrypted"] = encrypt_secret(password)
    host = ctx.db.hosts.update(host_id, **allowed)
    new_group_id = payload.get("group_id")
    if new_group_id is not None:
        new_group_id = int(new_group_id) if new_group_id else None
        old_group_id = ctx.db.groups.first_group_id_for_host(host_id)
        if old_group_id != new_group_id:
            if old_group_id:
                ctx.db.groups.remove_host(old_group_id, host_id)
            if new_group_id:
                ctx.db.groups.add_host(new_group_id, host_id)
    host = model_to_dict(host)
    host["last_seen"] = host["last_seen_at"]
    host["group_id"] = ctx.db.groups.first_group_id_for_host(host_id)
    return _ok(host)


async def api_hosts_delete(request: web.Request) -> web.Response:
    ctx = _ctx(request)
    payload = await _read_json(request)
    host_id = _safe_int(payload.get("id"))
    ctx.db.hosts.delete(host_id)
    return _ok({"deleted": host_id})


async def api_hosts_check(request: web.Request) -> web.Response:
    ctx = _ctx(request)
    payload = await _read_json(request)
    host_id = _safe_int(payload.get("id"))
    result = await ctx.host_service.check_host_async(host_id)
    host = model_to_dict(ctx.db.hosts.get(host_id))
    host["last_seen"] = host["last_seen_at"]
    host["group_id"] = ctx.db.groups.first_group_id_for_host(host_id)
    result["host"] = host
    return _ok(result)


async def api_hosts_check_all(request: web.Request) -> web.Response:
    ctx = _ctx(request)
    await _read_json(request)
    result = await ctx.host_service.check_all_hosts_async()
    hosts = []
    for host in ctx.db.hosts.all():
        item = model_to_dict(host)
        item["last_seen"] = host.last_seen_at
        item["group_id"] = ctx.db.groups.first_group_id_for_host(host.id)
        hosts.append(item)
    result["hosts"] = hosts
    return _ok(result)


async def api_hosts_reprovision(request: web.Request) -> web.Response:
    """Заново копирует SSH-ключ на хост (при отвале/удалении ключа).

    Использует сохранённый пароль хоста; если в запросе передан новый пароль —
    берёт его и (при успехе) обновляет сохранённое значение. По умолчанию
    копируется текущий привязанный ключ хоста; если передан ``ssh_key_id`` —
    копируется выбранный ключ, и он же становится новым привязанным ключом
    хоста (иначе netrunner продолжил бы ходить старым ключом, а на машину был
    бы скопирован другой).
    """
    ctx = _ctx(request)
    payload = await _read_json(request)
    host_id = _safe_int(payload.get("id"))
    host = ctx.db.hosts.get(host_id)
    if not host:
        return _error("Хост не найден", status=404)

    new_password = str(payload.get("password") or "").strip() or None
    password = new_password or ctx.host_service.get_host_password(host_id)
    if not password:
        return _error(
            "Для хоста не сохранён пароль — укажите пароль для перепривязки ключа",
            status=400,
        )

    raw_key_id = payload.get("ssh_key_id")
    ssh_key_id = int(raw_key_id) if raw_key_id else host.ssh_key_id

    await _provision_ssh_key(
        ctx, host.username, host.address, host.port, password, ssh_key_id
    )
    # Перепривязка удалась — сохраняем пароль (если был передан новый), сам
    # выбранный ключ (если он отличается от текущего) и проверяем доступность
    # хоста по обновлённому ключу.
    if new_password:
        ctx.host_service.set_host_password(host_id, new_password)
    if ssh_key_id != host.ssh_key_id:
        ctx.db.hosts.update(host_id, ssh_key_id=ssh_key_id)
    check = await ctx.host_service.check_host_async(host_id)
    item = model_to_dict(ctx.db.hosts.get(host_id))
    item["last_seen"] = item["last_seen_at"]
    item["group_id"] = ctx.db.groups.first_group_id_for_host(host_id)
    return _ok({"host": item, "is_active": check.get("is_active")})