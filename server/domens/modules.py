import json

from aiohttp import web

from server.tools import _ctx, _ok, model_to_dict, _read_json, _safe_int
from services.module_registry import _install_uploaded_module


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
        item["web_ui_visible"] = getattr(runtime, "web_ui_visible", True) if runtime else True
        item["admin_only"] = admin_only
        modules.append(item)
    return _ok(modules)


async def api_modules_create(request: web.Request) -> web.Response:
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

    return _ok(module)


async def api_modules_update(request: web.Request) -> web.Response:
    ctx = _ctx(request)
    payload = await _read_json(request)
    module_id = _safe_int(payload.get("id"))
    updates = {k: v for k, v in payload.items() if k != "id" and v is not None}
    if "is_enabled" in payload:
        updates["is_enabled"] = 1 if payload["is_enabled"] else 0
    module = ctx.db.modules.update(module_id, **updates)
    return _ok(module)


async def api_modules_delete(request: web.Request) -> web.Response:
    ctx = _ctx(request)
    payload = await _read_json(request)
    module_id = _safe_int(payload.get("id"))
    ctx.db.modules.delete(module_id)
    return _ok({"deleted": module_id})