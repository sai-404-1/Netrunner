from __future__ import annotations

import asyncio
import json
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

from aiohttp import web

from database.db_transfer import (
    ALL_TABLE_NAMES,
    export_tables,
    list_tables_with_counts,
    merge_database,
)


def _require_superuser(request: web.Request) -> None:
    user = request.get("auth_user")
    if not user or not user.get("is_superuser"):
        raise web.HTTPForbidden(
            body=json.dumps({"ok": False, "error": "Admin access required"}, ensure_ascii=False),
            content_type="application/json",
        )


def _ctx(request: web.Request):
    return request.app["ctx"]


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


async def _read_json(request: web.Request) -> dict[str, Any]:
    try:
        data = await request.json()
    except Exception as exc:
        raise web.HTTPBadRequest(
            body=json.dumps({"ok": False, "error": f"Invalid JSON: {exc}"}, ensure_ascii=False),
            content_type="application/json",
        )
    return data if isinstance(data, dict) else {}


def _user_safe(user) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "is_active": user.is_active,
        "is_superuser": user.is_superuser,
        "role": getattr(user, "role", "user"),
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


async def api_admin_users_list(request: web.Request) -> web.Response:
    _require_superuser(request)
    db = _ctx(request).db
    users = db.users.all()
    return _json_response({"ok": True, "data": [_user_safe(u) for u in users]})


async def api_admin_users_create(request: web.Request) -> web.Response:
    _require_superuser(request)
    payload = await _read_json(request)
    auth = _auth_service(request)
    result = auth.register(
        username=str(payload.get("username") or "").strip(),
        password=str(payload.get("password") or ""),
        role=str(payload.get("role") or "user").strip(),
    )
    return _json_response(result, status=201 if result.get("ok") else 400)


async def api_admin_users_update(request: web.Request) -> web.Response:
    _require_superuser(request)
    payload = await _read_json(request)
    user_id = payload.get("id")
    if not user_id:
        return _json_response({"ok": False, "error": "id required"}, status=400)
    db = _ctx(request).db
    target = db.users.get(int(user_id))
    if not target:
        return _json_response({"ok": False, "error": "Пользователь не найден"}, status=404)
    # Бутстрап-аккаунт admin/admin (is_superuser=1, роль ещё не 'admin') защищён от
    # смены роли через этот эндпоинт — иначе можно случайно остаться без единственного
    # суперпользователя. Роль 'admin', назначенная явно другому аккаунту, меняется
    # свободно, как обычная роль.
    is_bootstrap_admin = bool(target.is_superuser) and target.role != "admin"

    update_data = {}
    if "is_active" in payload:
        update_data["is_active"] = int(bool(payload["is_active"]))
    if "role" in payload and str(payload["role"]) in ("user", "teacher", "admin"):
        if is_bootstrap_admin:
            return _json_response(
                {"ok": False, "error": "Нельзя изменить роль главного администратора"}, status=400
            )
        new_role = str(payload["role"])
        update_data["role"] = new_role
        # Роль 'admin' — то же самое право, что и is_superuser у бутстрап-аккаунта;
        # уход из роли 'admin' его снимает.
        update_data["is_superuser"] = 1 if new_role == "admin" else 0
    if not update_data:
        return _json_response({"ok": False, "error": "Nothing to update"}, status=400)
    updated = db.users.update(int(user_id), **update_data)
    return _json_response({"ok": True, "data": _user_safe(updated)})


async def api_admin_users_delete(request: web.Request) -> web.Response:
    _require_superuser(request)
    payload = await _read_json(request)
    user_id = payload.get("id")
    if not user_id:
        return _json_response({"ok": False, "error": "id required"}, status=400)
    caller = request.get("auth_user")
    if caller and caller["id"] == int(user_id):
        return _json_response({"ok": False, "error": "Cannot delete yourself"}, status=400)
    db = _ctx(request).db
    ok = db.users.delete(int(user_id))
    return _json_response({"ok": ok})


async def api_admin_user_modules(request: web.Request) -> web.Response:
    _require_superuser(request)
    user_id = request.rel_url.query.get("user_id")
    if not user_id:
        return _json_response({"ok": False, "error": "user_id required"}, status=400)
    user_id = int(user_id)
    db = _ctx(request).db
    all_modules = db.modules.all()
    access_rows = {row.module_id: row.allowed for row in db.user_module_access.by_user(user_id)}
    result = []
    for mod in all_modules:
        result.append({
            "module_id": mod.id,
            "name": mod.name,
            "slug": mod.slug,
            "is_enabled": mod.is_enabled,
            "allowed": access_rows.get(mod.id, 1),
        })
    return _json_response({"ok": True, "data": result})


async def api_admin_user_modules_set(request: web.Request) -> web.Response:
    _require_superuser(request)
    payload = await _read_json(request)
    user_id = payload.get("user_id")
    module_id = payload.get("module_id")
    allowed = payload.get("allowed")
    if user_id is None or module_id is None or allowed is None:
        return _json_response({"ok": False, "error": "user_id, module_id, allowed required"}, status=400)
    db = _ctx(request).db
    db.user_module_access.set_access(int(user_id), int(module_id), int(bool(allowed)))
    return _json_response({"ok": True})


async def api_admin_user_groups(request: web.Request) -> web.Response:
    _require_superuser(request)
    user_id = request.rel_url.query.get("user_id")
    if not user_id:
        return _json_response({"ok": False, "error": "user_id required"}, status=400)
    user_id = int(user_id)
    db = _ctx(request).db
    all_groups = db.groups.all()
    granted_ids = {row.group_id for row in db.user_group_access.by_user(user_id)}
    result = [
        {"group_id": g.id, "name": g.name, "kind": g.kind, "granted": g.id in granted_ids}
        for g in all_groups
    ]
    return _json_response({"ok": True, "data": result})


async def api_admin_user_groups_set(request: web.Request) -> web.Response:
    _require_superuser(request)
    payload = await _read_json(request)
    user_id = payload.get("user_id")
    group_id = payload.get("group_id")
    granted = payload.get("granted")
    if user_id is None or group_id is None or granted is None:
        return _json_response({"ok": False, "error": "user_id, group_id, granted required"}, status=400)
    db = _ctx(request).db
    db.user_group_access.set_access(int(user_id), int(group_id), bool(granted))
    return _json_response({"ok": True})


async def api_admin_db_tables(request: web.Request) -> web.Response:
    """Список таблиц NetRunner с количеством строк — для UI выбора таблиц бэкапа."""
    _require_superuser(request)
    db_path = str(_ctx(request).db.db_path)
    tables = await asyncio.to_thread(list_tables_with_counts, db_path)
    return _json_response({"ok": True, "data": tables})


async def api_admin_backup(request: web.Request) -> web.Response:
    """Резервное копирование.

    Без параметров — полный бэкап (SQLite Online Backup API).
    ?tables=a,b,c — частичный бэкап: валидная база с полной схемой и строками
    только выбранных таблиц.
    """
    _require_superuser(request)
    db_path = str(_ctx(request).db.db_path)

    tables_param = request.rel_url.query.get("tables", "").strip()
    selected = [t for t in (s.strip() for s in tables_param.split(",")) if t]
    # "all" или пустой список означают полный бэкап
    partial = bool(selected) and "all" not in selected
    if partial:
        invalid = [t for t in selected if t not in ALL_TABLE_NAMES]
        if invalid:
            return _json_response(
                {"ok": False, "error": f"Неизвестные таблицы: {', '.join(invalid)}"},
                status=400,
            )

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    tmp_path = tmp.name
    try:
        if partial:
            await asyncio.to_thread(export_tables, db_path, tmp_path, selected)
            filename = "netrunner_backup_partial.db"
        else:
            await asyncio.to_thread(_do_backup, db_path, tmp_path)
            filename = "netrunner_backup.db"
        data = Path(tmp_path).read_bytes()
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return web.Response(
        body=data,
        status=200,
        content_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _do_backup(src_path: str, dest_path: str) -> None:
    src = sqlite3.connect(src_path)
    dest = sqlite3.connect(dest_path)
    try:
        src.backup(dest)
    finally:
        dest.close()
        src.close()


_RESTORE_MODES = ("classic", "replace", "append")


async def api_admin_restore(request: web.Request) -> web.Response:
    """Восстановление базы. Способ задаётся полем ``mode`` (multipart):

    classic — классическое: полная замена файла БД (деструктивно);
    replace — перезапись записей с тем же id (INSERT OR REPLACE);
    append  — дополнение: вставка с новым id и перепривязкой внешних ключей.

    После любого режима бэкенд перезапускается, чтобы реестр модулей и кэши
    подхватили изменения.
    """
    _require_superuser(request)
    ctx = _ctx(request)

    reader = await request.multipart()
    mode = "classic"
    tmp_path: str | None = None
    try:
        async for part in reader:
            if part.name == "mode":
                mode = (await part.text()).strip() or "classic"
            elif part.name == "file":
                tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
                tmp.close()
                tmp_path = tmp.name
                with open(tmp_path, "wb") as f:
                    while True:
                        chunk = await part.read_chunk(65536)
                        if not chunk:
                            break
                        f.write(chunk)

        if tmp_path is None:
            return _json_response({"ok": False, "error": "Поле file обязательно"}, status=400)
        if mode not in _RESTORE_MODES:
            return _json_response(
                {"ok": False, "error": f"Неизвестный режим восстановления: {mode}"}, status=400
            )

        # Проверяем целостность и принадлежность к NetRunner
        check_conn = sqlite3.connect(tmp_path)
        try:
            result = check_conn.execute("PRAGMA integrity_check").fetchone()
            if result[0] != "ok":
                return _json_response({"ok": False, "error": f"Файл повреждён: {result[0]}"}, status=400)
            tables = {r[0] for r in check_conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            if "users" not in tables or "hosts" not in tables:
                return _json_response({"ok": False, "error": "Файл не является резервной копией NetRunner"}, status=400)
        finally:
            check_conn.close()

        db_path = str(ctx.db.db_path)
        # Перед любой операцией сохраняем текущую базу — путь отката.
        await asyncio.to_thread(shutil.copy2, db_path, db_path + ".pre_restore")

        if mode == "classic":
            await asyncio.to_thread(shutil.copy2, tmp_path, db_path)
            message = "База восстановлена (классическое). Сервер перезапускается..."
            summary = None
        else:
            summary = await asyncio.to_thread(merge_database, db_path, tmp_path, mode)
            label = "замена по id" if mode == "replace" else "дополнение"
            message = f"База восстановлена ({label}). Сервер перезапускается..."
    finally:
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    # Перезапускаем Python-бэкенд — startup.sh поднимет его снова
    asyncio.get_event_loop().call_later(0.5, _restart_backend)
    return _json_response({"ok": True, "message": message, "summary": summary})


def _restart_backend() -> None:
    import signal
    os.kill(os.getpid(), signal.SIGTERM)


async def api_admin_host_agents(request: web.Request) -> web.Response:
    """Статус endpoint-агентов (host_agents) по всем хостам — для наблюдаемости."""
    _require_superuser(request)
    db = _ctx(request).db
    rows = db.host_agents.all()
    data = [
        {
            "host_id": r.host_id,
            "ssh_username": r.ssh_username,
            "status": r.status,
            "last_seen_at": r.last_seen_at,
            "created_at": r.created_at,
        }
        for r in rows
    ]
    return _json_response({"ok": True, "data": data})


async def api_admin_host_events(request: web.Request) -> web.Response:
    """Журнал статусных событий агентов (host_events). ?host_id= фильтрует по хосту."""
    _require_superuser(request)
    db = _ctx(request).db
    host_id = request.rel_url.query.get("host_id")
    limit = int(request.rel_url.query.get("limit", 200))
    rows = db.host_events.for_host(int(host_id), limit=limit) if host_id else db.host_events.recent(limit=limit)
    data = [
        {
            "id": r.id,
            "host_id": r.host_id,
            "type": r.type,
            "payload_json": r.payload_json,
            "created_at": r.created_at,
        }
        for r in rows
    ]
    return _json_response({"ok": True, "data": data})
