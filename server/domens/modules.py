import json

import sqlite3

from aiohttp import web

from server.tools import _ctx, _ok, _error, model_to_dict, _read_json, _safe_int
from services.module_registry import _install_uploaded_module


def _require_superuser(request: web.Request):
    """None, если можно менять модули; иначе готовый ответ 403.

    create/update/delete не проверяли роль вовсе — только факт логина.
    create принимает file_data и исполняет загруженный .py НА СЕРВЕРЕ
    (_install_uploaded_module делает exec_module сразу), т.е. это
    исполнение произвольного Python любым залогиненным пользователем,
    вплоть до "user" без единой привилегии. update/delete прикрыты той же
    проверкой для единообразия и на будущее — команда в schema_json тоже
    исполняется, просто не на сервере, а на выбранном пользователем хосте.
    """
    user = request.get("auth_user")
    if user and user.get("is_superuser"):
        return None
    return _error("Управление модулями доступно только администратору", status=403)


async def api_modules(request: web.Request) -> web.Response:
    db = _ctx(request).db
    user = request.get("auth_user")
    denied_ids: set[int] = set()
    if user and not user.get("is_superuser"):
        for row in db.user_module_access.by_user(user["id"]):
            if not row.allowed:
                denied_ids.add(row.module_id)
    modules = []
    runtime_modules = {item.slug: item for item in _ctx(request).module_registry.all()}
    for row in db.modules.all():
        if row.id in denied_ids:
            continue
        runtime = runtime_modules.get(row.slug)
        admin_only = bool(getattr(runtime.instance, "admin_only", False)) if runtime else False
        # Модули «только для админа» обычным пользователям не показываем.
        if admin_only and not (user and user.get("is_superuser")):
            continue
        item = model_to_dict(row)
        item["supports_task_runner"] = bool(runtime and runtime.supports_task_runner)
        # Почему модуль (не) попадает в списки запуска на хостах и в сценариях:
        # страница модулей показывает строки БД, а запуск видит только реестр.
        if runtime is None:
            item["run_status"] = "not_loaded"
        elif not runtime.supports_task_runner:
            item["run_status"] = "console_only"
        else:
            item["run_status"] = "ok"
        item["web_ui_visible"] = getattr(runtime, "web_ui_visible", True) if runtime else True
        item["admin_only"] = admin_only
        modules.append(item)
    return _ok(modules)


def _require_superuser(request: web.Request):
    """None, если можно менять модули; иначе готовый ответ 403.

    Раньше create/update/delete не проверяли роль вовсе — не будило вопросов,
    пока модуль-команда без .py-файла не запускался НИКОГДА (регистрация в
    реестр появилась только с register_db_command_module). Теперь такой
    модуль исполняется как обычный, а /api/run авторизует только по доступу к
    хосту, не по тому, кто его завёл — без этой проверки любой залогиненный
    "user" мог бы создать команду и выполнить её на доступных ему машинах.
    """
    user = request.get("auth_user")
    if user and user.get("is_superuser"):
        return None
    return _error("Управление модулями доступно только администратору", status=403)


async def api_modules_create(request: web.Request) -> web.Response:
    denied = _require_superuser(request)
    if denied:
        return denied
    ctx = _ctx(request)
    payload = await _read_json(request)
    name = str(payload.get("name") or "").strip()
    slug = str(payload.get("slug") or "").strip()
    module_path = str(payload.get("module_path") or "").strip()
    class_name = str(payload.get("class_name") or "").strip() or "UserModule"
    description = str(payload.get("description") or "").strip() or None
    file_data = str(payload.get("file_data") or "").strip() or None

    schema_json = payload.get("schema_json") or None

    module = ctx.db.modules.create(
        name=name,
        slug=slug,
        module_path=module_path,
        class_name=class_name,
        is_builtin=0,
        is_enabled=1,
        description=description,
        schema_json=schema_json,
    )

    if file_data:
        try:
            _install_uploaded_module(ctx, slug, module_path, file_data, name=name, description=description)
        except Exception as exc:
            ctx.db.modules.delete(module.id)
            raise web.HTTPBadRequest(
                body=json.dumps({"ok": False, "error": f"Не удалось загрузить модуль: {exc}"}, ensure_ascii=False)
            )
    else:
        # Модуль-команда без файла: сразу делаем запускаемым, без перезапуска.
        ctx.module_registry.register_db_command_module(module)

    return _ok(module)


async def api_modules_update(request: web.Request) -> web.Response:
    denied = _require_superuser(request)
    if denied:
        return denied
    ctx = _ctx(request)
    payload = await _read_json(request)
    module_id = _safe_int(payload.get("id"))
    updates = {k: v for k, v in payload.items() if k != "id" and v is not None}
    if "is_enabled" in payload:
        updates["is_enabled"] = 1 if payload["is_enabled"] else 0
    before = ctx.db.modules.get(module_id)
    try:
        module = ctx.db.modules.update(module_id, **updates)
    except sqlite3.IntegrityError:
        return _error(f"Модуль со slug «{updates.get('slug')}» уже существует")
    if before is not None and module is not None:
        if before.slug != module.slug:
            ctx.module_registry.unregister_db_defined(before.slug)
        # Правка команды/полей модуля-команды применяется сразу.
        ctx.module_registry.register_db_command_module(module)
    return _ok(module)


async def api_modules_delete(request: web.Request) -> web.Response:
    denied = _require_superuser(request)
    if denied:
        return denied
    ctx = _ctx(request)
    payload = await _read_json(request)
    module_id = _safe_int(payload.get("id"))
    row = ctx.db.modules.get(module_id)
    ctx.db.modules.delete(module_id)
    if row is not None:
        ctx.module_registry.unregister_db_defined(row.slug)
    return _ok({"deleted": module_id})