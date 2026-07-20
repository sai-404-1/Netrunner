from __future__ import annotations

"""Async web server for NetRunner.

This module replaces the previous single-threaded http.server implementation
with an aiohttp-based async server. Long-running operations (task execution,
host checks, scheduler ticks) are dispatched as background asyncio tasks so the
HTTP API stays responsive.

Start the server from the project root:

    python -m web_main

or with custom options:

    python -m web_main --host 0.0.0.0 --port 8000 --db data/netrunner.db

Public API additions:
    POST /api/run                -> returns immediately {run_id, status}
    GET  /api/run/{id}/status    -> poll task status and per-host results
    WS   /ws                     -> receive task status updates
"""

import asyncio
import base64
import hashlib
import importlib.util
import json
import logging
import os
import re
import subprocess
import sys
import traceback
import uuid
import webbrowser
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from aiohttp import web
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa
from cryptography.hazmat.primitives.serialization import BestAvailableEncryption, NoEncryption

from computer.module.executor_ssh import _ssh_common_options
from database import open_database
from database.repos.base import utcnow_iso
from services import HostService
from services.auth_service import AuthService
from services.secrets import encrypt_secret
from services.update_service import UpdateService
from services.telegram_service import TelegramService
from webui.auth_handlers import (
    api_login,
    api_login_verify,
    api_logout,
    api_me,
    api_me_update,
    api_register,
)
from webui.auth_middleware import auth_middleware
from webui.admin_handlers import (
    api_admin_users_list,
    api_admin_users_create,
    api_admin_users_update,
    api_admin_users_delete,
    api_admin_user_modules,
    api_admin_user_modules_set,
    api_admin_user_groups,
    api_admin_user_groups_set,
    api_admin_db_tables,
    api_admin_backup,
    api_admin_restore,
    api_admin_host_agents,
    api_admin_host_events,
)
from webui.board_handlers import (
    api_boards_list,
    api_boards_create,
    api_boards_get,
    api_boards_update,
    api_boards_delete,
    api_boards_save_layout,
)
from webui.terminal_handler import api_terminal_ws


STATIC_DIR = Path(__file__).resolve().parent / "static"
logger = logging.getLogger("netrunner")


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


def _json_response(data: Any, status: int = 200) -> web.Response:
    body = json.dumps(model_to_dict(data), ensure_ascii=False, default=str).encode("utf-8")
    return web.Response(
        body=body,
        status=status,
        content_type="application/json",
        charset="utf-8",
    )


def _ok(data: Any) -> web.Response:
    return _json_response({"ok": True, "data": data})


def _error(message: str, status: int = 400) -> web.Response:
    return _json_response({"ok": False, "error": message}, status=status)


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


async def _run_background(app: web.Application, coro):
    """Schedule a coroutine as a tracked background task."""
    task = asyncio.create_task(coro)
    app["background_tasks"].add(task)
    task.add_done_callback(lambda t: app["background_tasks"].discard(t))


async def _broadcast_task_update(app: web.Application, run_id: int):
    """Push the latest task-run state to every connected WebSocket client."""
    run = app["ctx"].db.task_runs.get(run_id)
    if run is None:
        return
    message = json.dumps({"type": "task_status", "run": model_to_dict(run)}, ensure_ascii=False, default=str)
    dead = set()
    for ws in app["websockets"]:
        try:
            await ws.send_str(message)
        except Exception:
            dead.add(ws)
    app["websockets"].difference_update(dead)


# ---------------------------------------------------------------------------
# Static files and reports
# ---------------------------------------------------------------------------

async def healthz_handler(request: web.Request) -> web.Response:
    """Публичный health-check для супервизора (см. supervise.py)."""
    return web.json_response({"ok": True})


async def index_handler(request: web.Request) -> web.Response:
    return web.FileResponse(STATIC_DIR / "index.html")


async def reports_handler(request: web.Request) -> web.Response:
    report_path = request.match_info["path"]
    reports_dir = Path(_ctx(request).reports_dir).resolve()
    target = (reports_dir / report_path).resolve()
    if not target.is_relative_to(reports_dir):
        return _error("Forbidden", status=403)
    if not target.exists() or target.is_dir():
        return _error("Not found", status=404)
    return web.FileResponse(target)


# ---------------------------------------------------------------------------
# API GET handlers
# ---------------------------------------------------------------------------

async def api_summary(request: web.Request) -> web.Response:
    db = _ctx(request).db
    task_runs = db.task_runs.list_recent(10)
    inventory = db.inventory.all(order_by="collected_at DESC")
    reports = db.reports.latest(5)

    # Per-group stats
    all_hosts = db.hosts.all()
    all_groups = db.groups.all()
    group_stats = []
    for group in all_groups:
        hosts = db.groups.hosts(group.id)
        total = len(hosts)
        online = sum(1 for h in hosts if getattr(h, 'is_active', False))
        group_stats.append({
            "id": group.id,
            "name": group.name,
            "kind": group.kind,
            "total": total,
            "online": online,
            "offline": total - online,
        })

    data = {
        "hosts": len(all_hosts),
        "hosts_online": sum(1 for h in all_hosts if h.is_active),
        "groups": len(all_groups),
        "modules": len(db.modules.all()),
        "task_runs": len(db.task_runs.all()),
        "inventory": len(inventory),
        "scheduled": len(db.scheduled.all()),
        "reports": len(db.reports.all()),
        "recent_task_runs": task_runs,
        "latest_inventory": inventory[:5],
        "latest_reports": reports,
        "group_stats": group_stats,
    }
    return _ok(data)


async def api_hosts(request: web.Request) -> web.Response:
    db = _ctx(request).db
    user = request.get("auth_user")
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
    return _ok(hosts)


async def api_groups(request: web.Request) -> web.Response:
    db = _ctx(request).db
    groups = []
    for group in db.groups.all():
        item = model_to_dict(group)
        item["hosts"] = db.groups.hosts(group.id)
        groups.append(item)
    return _ok(groups)


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


async def api_task_templates(request: web.Request) -> web.Response:
    return _ok(_ctx(request).db.task_templates.all())


async def api_task_runs(request: web.Request) -> web.Response:
    limit = _safe_int(request.query.get("limit", 50), 50)
    return _ok(_ctx(request).db.task_runs.list_recent(limit))


async def api_task_run_status(request: web.Request) -> web.Response:
    ctx = _ctx(request)
    run_id = _safe_int(request.match_info["id"])
    run = ctx.db.task_runs.get(run_id)
    if run is None:
        return _error("Task run not found", status=404)
    data = model_to_dict(run)
    # Прогресс: сколько хостов уже обработано (state ok|error) из общего числа.
    # per_host_json теперь содержит все цели с самого начала (queued/running/ok/error),
    # поэтому считаем именно завершённые. У записей без поля state (sync-модули/легаси)
    # state по умолчанию «ok» — они уже финальные.
    done = 0
    total = 0
    if run.per_host_json:
        try:
            items = json.loads(run.per_host_json)
            total = len(items)
            done = sum(1 for it in items if it.get("state", "ok") in ("ok", "error"))
        except Exception:
            done = total = 0
    if total == 0:
        try:
            total = len(ctx.host_service.resolve_targets(run.target_type, run.target_id))
        except Exception:
            total = 0
    data["progress"] = {"done": done, "total": total}
    return _ok(data)


async def api_inventory(request: web.Request) -> web.Response:
    return _ok(_ctx(request).db.inventory.all(order_by="collected_at DESC"))


async def api_scheduled(request: web.Request) -> web.Response:
    return _ok(_ctx(request).db.scheduled.all())


async def api_reports(request: web.Request) -> web.Response:
    report_type = request.query.get("type")
    return _ok(_ctx(request).db.reports.latest(50, report_type=report_type))


async def api_system_logs(request: web.Request) -> web.Response:
    """Журнал внутренних процессов сервера («История» → «Логи»): попытки
    автоустановки агента и т.п."""
    limit = _safe_int(request.query.get("limit"), 200)
    return _ok(_ctx(request).db.system_logs.recent(limit=limit))


async def api_ssh_keys(request: web.Request) -> web.Response:
    keys = []
    for key in _ctx(request).db.ssh_keys.all():
        item = model_to_dict(key)
        item.pop("private_key", None)
        keys.append(item)
    return _ok(keys)


# ---------------------------------------------------------------------------
# API POST handlers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Загруженные файлы (для модуля рассылки файлов). Только для администратора.
# ---------------------------------------------------------------------------

def _require_admin(request: web.Request) -> bool:
    user = request.get("auth_user")
    return bool(user and user.get("is_superuser"))


def _uploads_dir() -> Path:
    try:
        from config import UPLOADS_PATH
    except Exception:
        UPLOADS_PATH = "uploads"
    directory = Path(UPLOADS_PATH)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _upload_to_dict(row) -> dict:
    return {
        "id": row.id,
        "name": row.original_name,
        "size_bytes": row.size_bytes,
        "uploaded_by": row.uploaded_by,
        "created_at": row.created_at,
    }


async def api_uploads_list(request: web.Request) -> web.Response:
    if not _require_admin(request):
        return _error("Только для администратора", status=403)
    rows = _ctx(request).db.uploaded_files.recent(500)
    return _ok([_upload_to_dict(r) for r in rows])


async def api_uploads_create(request: web.Request) -> web.Response:
    if not _require_admin(request):
        return _error("Только для администратора", status=403)
    ctx = _ctx(request)
    user = request.get("auth_user")
    uploaded_by = user.get("username") if user else None
    uploads_dir = _uploads_dir()

    reader = await request.multipart()
    saved = []
    async for part in reader:
        filename = part.filename
        if not filename:
            await part.read()  # сливаем не-файловые поля
            continue
        safe = Path(filename).name or "file"
        target = uploads_dir / f"{uuid.uuid4().hex}_{safe}"
        size = 0
        with target.open("wb") as fh:
            while True:
                chunk = await part.read_chunk()
                if not chunk:
                    break
                size += len(chunk)
                fh.write(chunk)
        row = ctx.db.uploaded_files.create(
            original_name=safe,
            stored_path=str(target),
            size_bytes=size,
            uploaded_by=uploaded_by,
        )
        saved.append(_upload_to_dict(row))

    if not saved:
        return _error("Файлы не получены", status=400)
    return _ok(saved)


async def api_uploads_download(request: web.Request) -> web.Response:
    if not _require_admin(request):
        return _error("Только для администратора", status=403)
    row = _ctx(request).db.uploaded_files.get(_safe_int(request.match_info["id"]))
    if not row:
        return _error("Файл не найден", status=404)
    target = Path(row.stored_path)
    if not target.exists():
        return _error("Файл отсутствует на диске", status=404)
    return web.FileResponse(
        target,
        headers={"Content-Disposition": f'attachment; filename="{row.original_name}"'},
    )


async def api_uploads_delete(request: web.Request) -> web.Response:
    if not _require_admin(request):
        return _error("Только для администратора", status=403)
    ctx = _ctx(request)
    payload = await _read_json(request)
    file_id = _safe_int(payload.get("id"))
    row = ctx.db.uploaded_files.get(file_id)
    if not row:
        return _error("Файл не найден", status=404)
    try:
        Path(row.stored_path).unlink(missing_ok=True)
    except OSError:
        pass
    ctx.db.uploaded_files.delete(file_id)
    return _ok({"deleted": file_id})


# ---------------------------------------------------------------------------
# Обновление кода (git-монитор, Phase 2). Только для администратора.
# ---------------------------------------------------------------------------

def _update_check_blocking(db_path):
    """Создаёт собственное соединение с БД в рабочем потоке (sqlite не потокобезопасен)."""
    db = open_database(db_path)
    try:
        return UpdateService(db).check()
    finally:
        db.close()


async def api_update_status(request: web.Request) -> web.Response:
    if not _require_admin(request):
        return _error("Только для администратора", status=403)
    cfg = UpdateService(_ctx(request).db).get_config()
    return _ok({"config": cfg, "status": request.app.get("update_status")})


async def api_update_recheck(request: web.Request) -> web.Response:
    if not _require_admin(request):
        return _error("Только для администратора", status=403)
    result = await asyncio.to_thread(_update_check_blocking, _ctx(request).db_path)
    result["checked_at"] = utcnow_iso()
    request.app["update_status"] = result
    return _ok(result)


async def api_update_set_config(request: web.Request) -> web.Response:
    if not _require_admin(request):
        return _error("Только для администратора", status=403)
    payload = await _read_json(request)
    cfg = UpdateService(_ctx(request).db).set_config(
        remote=payload.get("remote"),
        branch=payload.get("branch"),
        token=payload.get("token"),  # None — не менять, "" — очистить
        auto_update=payload.get("auto_update"),
        poll_interval=payload.get("poll_interval"),
    )
    return _ok(cfg)


async def api_update_incidents(request: web.Request) -> web.Response:
    """Последние инциденты супервизора (краши/recovery) и хвост его лога."""
    if not _require_admin(request):
        return _error("Только для администратора", status=403)
    from services.update_service import DATA_DIR

    incidents = []
    inc_dir = DATA_DIR / "incidents"
    if inc_dir.exists():
        for f in sorted(inc_dir.glob("*.log"), reverse=True)[:20]:
            try:
                incidents.append({"name": f.name, "content": f.read_text(encoding="utf-8")[:4000]})
            except OSError:
                pass
    log_tail = ""
    log_file = DATA_DIR / "supervisor.log"
    if log_file.exists():
        try:
            log_tail = "\n".join(log_file.read_text(encoding="utf-8").splitlines()[-100:])
        except OSError:
            pass
    return _ok({"incidents": incidents, "log_tail": log_tail})


async def api_update_apply(request: web.Request) -> web.Response:
    if not _require_admin(request):
        return _error("Только для администратора", status=403)

    def _work(db_path):
        db = open_database(db_path)
        try:
            return UpdateService(db).apply()
        finally:
            db.close()

    result = await asyncio.to_thread(_work, _ctx(request).db_path)
    if result.get("ok"):
        # Завершаем процесс после ответа — супервизор пересоберёт фронт и поднимет новый код.
        async def _exit_soon():
            await asyncio.sleep(1.0)
            os._exit(0)

        await _run_background(request.app, _exit_soon())
    return _ok(result)


# ---------------------------------------------------------------------------
# Telegram: привязка/верификация аккаунта (личный кабинет) + конфиг бота (админ).
# ---------------------------------------------------------------------------

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


# --- доверенные устройства (2FA step-up) -----------------------------------
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

    def _work(db_path, action):
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


async def api_groups_create(request: web.Request) -> web.Response:
    import sqlite3 as _sqlite3
    ctx = _ctx(request)
    payload = await _read_json(request)
    name = str(payload.get("name") or "").strip()
    if not name:
        return _error("Название группы не может быть пустым")
    try:
        group = ctx.host_service.create_group(
            name=name,
            kind=str(payload.get("kind") or "custom").strip() or "custom",
            description=str(payload.get("description") or "").strip() or None,
        )
    except _sqlite3.IntegrityError:
        return _error(f"Группа с названием «{name}» уже существует")
    return _ok(group)


async def api_groups_update(request: web.Request) -> web.Response:
    ctx = _ctx(request)
    payload = await _read_json(request)
    group_id = _safe_int(payload.get("id"))
    updates = {k: v for k, v in payload.items() if k != "id" and v is not None}
    group = ctx.db.groups.update(group_id, **updates)
    return _ok(group)


async def api_groups_delete(request: web.Request) -> web.Response:
    ctx = _ctx(request)
    payload = await _read_json(request)
    group_id = _safe_int(payload.get("id"))
    ctx.db.groups.delete(group_id)
    return _ok({"deleted": group_id})


async def api_groups_add_host(request: web.Request) -> web.Response:
    ctx = _ctx(request)
    payload = await _read_json(request)
    link = ctx.host_service.add_host_to_group(
        group_id=_safe_int(payload.get("group_id")),
        host_id=_safe_int(payload.get("host_id")),
    )
    return _ok(link)


async def api_run(request: web.Request) -> web.Response:
    """Start a task and return immediately. The real work runs in background."""
    ctx = _ctx(request)
    payload = await _read_json(request)
    args = payload.get("args") or {}
    if not isinstance(args, dict):
        return _error("args must be an object")

    module_slug = str(payload.get("module_slug") or "").strip()
    target_type = str(payload.get("target_type") or "host").strip()
    target_id = _safe_int(payload.get("target_id"))

    module_row = ctx.db.modules.by_slug(module_slug)
    if not module_row:
        return _error(f"Module '{module_slug}' not found", status=404)

    user = request.get("auth_user")
    # Модули «только для админа» запускает лишь суперпользователь.
    try:
        runtime = ctx.module_registry.get(module_slug)
    except KeyError:
        runtime = None
    if runtime and getattr(runtime.instance, "admin_only", False):
        if not (user and user.get("is_superuser")):
            return _error("Этот модуль доступен только администратору", status=403)
    created_by = user.get("username") if user else None
    # Create a pending task-run row so the client can poll it immediately.
    task_run = ctx.db.task_runs.create(
        module_id=module_row.id,
        target_type=target_type,
        target_id=target_id,
        args_json=json.dumps(args, ensure_ascii=False),
        trigger_type="manual",
        status="pending",
        created_by=created_by,
    )

    async def _background_task():
        try:
            await ctx.task_runner.run_async(
                task_run_id=task_run.id,
                module_slug=module_slug,
                target_type=target_type,
                target_id=target_id,
                args=args,
                trigger_type="manual",
                created_by=created_by,
            )
        except Exception as exc:
            logger.exception("Background task run %s failed: %s", task_run.id, exc)
        finally:
            await _broadcast_task_update(request.app, task_run.id)

    await _run_background(request.app, _background_task())
    await _broadcast_task_update(request.app, task_run.id)
    return _ok({"run_id": task_run.id, "status": task_run.status})


async def api_run_cancel(request: web.Request) -> web.Response:
    """Cancel a running or pending task run."""
    ctx = _ctx(request)
    run_id = _safe_int(request.match_info["id"])
    run = ctx.db.task_runs.get(run_id)
    if run is None:
        return _error("Task run not found", status=404)
    if run.status not in ("running", "pending"):
        return _error("Task is not active", status=400)

    cancelled = ctx.task_runner.cancel(run_id=run_id)
    return _ok({"cancelled": cancelled})


async def api_modules_create(request: web.Request) -> web.Response:
    ctx = _ctx(request)
    payload = await _read_json(request)
    name = str(payload.get("name") or "").strip()
    slug = str(payload.get("slug") or "").strip()
    module_path = str(payload.get("module_path") or "").strip()
    class_name = str(payload.get("class_name") or "").strip() or "UserModule"
    description = str(payload.get("description") or "").strip() or None
    file_data = payload.get("file_data")

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


async def api_schedule_create(request: web.Request) -> web.Response:
    ctx = _ctx(request)
    payload = await _read_json(request)
    run_at = str(payload.get("run_at") or "").strip()
    if not run_at:
        raise web.HTTPBadRequest(reason="run_at is required")
    interval_raw = payload.get("interval_seconds")
    max_runs_raw = payload.get("max_runs")
    scheduled = ctx.db.scheduled.create(
        name=str(payload.get("name") or "").strip(),
        template_id=_safe_int(payload.get("template_id")),
        target_type=str(payload.get("target_type") or "host").strip(),
        target_id=_safe_int(payload.get("target_id")),
        run_at=run_at,
        is_enabled=1 if payload.get("is_enabled", True) else 0,
        interval_seconds=int(interval_raw) if interval_raw else None,
        max_runs=int(max_runs_raw) if max_runs_raw else None,
    )
    return _ok(scheduled)


async def api_schedule_update(request: web.Request) -> web.Response:
    ctx = _ctx(request)
    payload = await _read_json(request)
    task_id = _safe_int(payload.get("id"))
    updates = {k: v for k, v in payload.items() if k != "id" and v is not None}
    if "is_enabled" in payload:
        updates["is_enabled"] = 1 if payload["is_enabled"] else 0
    if "template_id" in updates:
        updates["template_id"] = _safe_int(updates["template_id"])
    if "target_id" in updates:
        updates["target_id"] = _safe_int(updates["target_id"])
    scheduled = ctx.db.scheduled.update(task_id, **updates)
    return _ok(scheduled)


async def api_schedule_delete(request: web.Request) -> web.Response:
    ctx = _ctx(request)
    payload = await _read_json(request)
    task_id = _safe_int(payload.get("id"))
    ctx.db.scheduled.delete(task_id)
    return _ok({"deleted": task_id})


async def api_scheduler_tick(request: web.Request) -> web.Response:
    ctx = _ctx(request)
    await ctx.scheduler.tick_async()
    return _ok({"message": "Планировщик проверен"})


async def api_task_runs_clear(request: web.Request) -> web.Response:
    ctx = _ctx(request)
    await _read_json(request)
    ctx.db.task_runs.clear_all()
    return _ok({"cleared": True})


async def api_reports_clear(request: web.Request) -> web.Response:
    ctx = _ctx(request)
    await _read_json(request)
    ctx.db.reports.clear_all()
    return _ok({"cleared": True})


async def api_reports_export(request: web.Request) -> web.Response:
    ctx = _ctx(request)
    payload = await _read_json(request)
    task_run_id = payload.get("task_run_id")
    fmt = str(payload.get("format") or "txt")
    service = ctx.report_service
    if task_run_id is not None:
        report, file_path = service.export_from_task_run(_safe_int(task_run_id), fmt=fmt)
    else:
        report_type = str(payload.get("report_type") or "tasks")
        if report_type == "tasks":
            report, file_path = service.export_task_runs(fmt=fmt)
        elif report_type == "inventory":
            report, file_path = service.export_inventory(fmt=fmt)
        elif report_type == "host_status":
            report, file_path = service.export_host_status(fmt=fmt)
        elif report_type == "filesystem":
            report, file_path = service.export_filesystem(fmt=fmt)
        elif report_type == "task_history":
            report, file_path = service.export_task_history(fmt=fmt)
        else:
            return _error("report_type must be one of tasks, inventory, host_status, filesystem, task_history")
    return _ok({"report": model_to_dict(report), "file_path": str(file_path)})


async def api_ssh_keys_create(request: web.Request) -> web.Response:
    db = _ctx(request).db
    payload = await _read_json(request)
    name = str(payload.get("name") or "").strip()
    file_data = payload.get("file_data")
    if not name:
        return _error("SSH key name is required")
    if not file_data:
        return _error("SSH key file data is required")
    private_path = _save_ssh_key(name, file_data)
    public_path = private_path.with_suffix(".pub")
    public_key_path = str(public_path) if public_path.exists() else None
    key = db.ssh_keys.create(
        name=name,
        private_key_path=str(private_path),
        public_key_path=public_key_path,
        has_passphrase=0,
        is_default=0,
    )
    return _ok(key)


async def api_keys_generate(request: web.Request) -> web.Response:
    db = _ctx(request).db
    payload = await _read_json(request)
    name = str(payload.get("key_name") or "").strip()
    key_type = str(payload.get("key_type") or "").strip().lower()
    passphrase = str(payload.get("passphrase") or "").strip() or None
    if not name:
        return _error("SSH key name is required")
    if key_type not in ("rsa", "ed25519"):
        return _error("key_type must be rsa or ed25519")

    private_pem, public_openssh, fingerprint, has_passphrase = await asyncio.to_thread(
        _generate_ssh_key, key_type, passphrase
    )
    private_path, public_path = _write_generated_ssh_key(name, private_pem, public_openssh)
    # The private key is stored only in the encrypted file on disk; the plaintext
    # private key material is intentionally not persisted in the database so it
    # cannot be leaked through API responses or backups.
    key = db.ssh_keys.create(
        name=name,
        private_key_path=str(private_path),
        public_key_path=str(public_path),
        key_type=key_type,
        public_key=public_openssh,
        fingerprint=fingerprint,
        has_passphrase=has_passphrase,
        is_default=0,
    )
    return _ok(
        {
            "id": key.id,
            "name": key.name,
            "key_type": key.key_type,
            "public_key": key.public_key,
            "fingerprint": key.fingerprint,
            "created_at": key.created_at,
        }
    )


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

async def websocket_handler(request: web.Request) -> web.WebSocketResponse:
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    request.app["websockets"].add(ws)
    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                except Exception:
                    continue
                action = data.get("action")
                if action == "subscribe":
                    run_id = _safe_int(data.get("run_id"))
                    run = request.app["ctx"].db.task_runs.get(run_id)
                    if run is not None:
                        await ws.send_str(
                            json.dumps({"type": "task_status", "run": model_to_dict(run)}, ensure_ascii=False, default=str)
                        )
    finally:
        request.app["websockets"].discard(ws)
    return ws


async def agent_websocket_handler(request: web.Request) -> web.WebSocketResponse:
    """Приём соединений endpoint-агентов — не путать с /ws (клиент веб-панели).
    Агент сам звонит сюда исходящим соединением; сервер никогда не инициирует
    запрос к агенту и не шлёт ему ничего, кроме закрытия соединения при невалидном
    токене — report-only в обе стороны. Любой присланный агентом тип сообщения
    (кроме служебного "hello") просто журналируется как есть — новый тип статуса
    не требует изменений здесь, см. AgentService.record_event."""
    from services.agent_service import AgentService

    ws = web.WebSocketResponse()
    await ws.prepare(request)
    ctx = request.app["ctx"]
    agent_svc = AgentService(ctx.db)
    host_id: int | None = None
    try:
        async for msg in ws:
            if msg.type != web.WSMsgType.TEXT:
                continue
            try:
                data = json.loads(msg.data)
            except Exception:
                continue

            msg_type = data.get("type")

            if host_id is None:
                if msg_type != "hello":
                    await ws.close(code=4001, message=b"expected hello")
                    break
                candidate_id = _safe_int(data.get("host_id"))
                token = str(data.get("token") or "")
                if not candidate_id or not agent_svc.verify_token(candidate_id, token):
                    await ws.close(code=4003, message=b"invalid token")
                    break
                host_id = candidate_id
                agent_svc.record_connect(host_id)
                logger.info("Agent connected for host_id=%s", host_id)
                continue

            if msg_type:
                agent_svc.record_event(
                    host_id, msg_type, payload_json=json.dumps(data, ensure_ascii=False, default=str)
                )
    finally:
        if host_id is not None:
            agent_svc.record_disconnect(host_id)
            logger.info("Agent disconnected for host_id=%s", host_id)
    return ws


def _default_agent_ws_url() -> str:
    """Угадывает адрес сервера для конфига агента: LAN-IP этой машины + порт
    Next.js в Docker (3001) + префикс /api/python/, который проксируется на
    бэкенд. Эвристика для автоустановки при добавлении хоста — если она угадала
    неверно, администратор может перевыпустить агента вручную через модуль
    «Установка endpoint-агента» с явно указанным адресом."""
    import socket
    try:
        ip = socket.gethostbyname(socket.gethostname())
    except Exception:  # noqa: BLE001
        ip = "127.0.0.1"
    return f"ws://{ip}:3001/api/python/agent/ws"


async def _auto_install_agent(app: web.Application, host) -> None:
    """Фоновая попытка установки endpoint-агента сразу после добавления хоста.
    Не блокирует создание хоста и не считается ошибкой добавления — при неудаче
    (например, нет passwordless sudo) просто пишется запись в системные логи
    («История» → «Логи»), которую видно в UI."""
    ctx = app["ctx"]
    from computer.module.agent_provision import CustomModule as agent_provision_module
    from services.task_runner import ModuleContext

    module_ctx = ModuleContext(
        logger=logger, task_run_id=0, to_computer=ctx.host_service.to_computer, db=ctx.db,
    )
    server_ws_url = _default_agent_ws_url()
    try:
        result = await agent_provision_module.run_for_host(module_ctx, host, server_ws_url=server_ws_url)
    except Exception as exc:  # noqa: BLE001 — фон: любая ошибка = запись в лог, не падение сервера
        logger.warning("Auto agent install failed for host_id=%s: %s", host.id, exc)
        ctx.db.system_logs.record(
            "agent_install", "error", f"Хост «{host.name}»: {exc}", host_id=host.id,
        )
        return

    level = "error" if result.get("status") == "error" else "success"
    output = str(result.get("output") or "")[:4000]
    ctx.db.system_logs.record(
        "agent_install", level, f"Хост «{host.name}» ({server_ws_url}): {output}", host_id=host.id,
    )


# ---------------------------------------------------------------------------
# Helpers (SSH keys, module install, provisioning)
# ---------------------------------------------------------------------------

def _install_uploaded_module(
    ctx,
    slug: str,
    module_path: str,
    file_data: str,
    name: str | None = None,
    description: str | None = None,
) -> None:
    """Сохраняет загруженный .py-файл и импортирует класс UserModule в runtime."""
    modules_dir = Path("/app/modules")
    modules_dir.mkdir(parents=True, exist_ok=True)

    file_name = Path(module_path).name
    if not file_name.endswith(".py"):
        file_name = f"{slug}.py"
    target_path = modules_dir / file_name

    raw = base64.b64decode(file_data)
    target_path.write_bytes(raw)

    spec = importlib.util.spec_from_file_location(slug, str(target_path))
    if spec is None or spec.loader is None:
        raise RuntimeError("Не удалось создать spec для модуля")
    module = importlib.util.module_from_spec(spec)
    sys.modules[slug] = module
    spec.loader.exec_module(module)

    user_cls = getattr(module, "UserModule", None)
    if user_cls is None:
        raise RuntimeError("В модуле не найден класс UserModule")

    instance = user_cls()
    ctx.module_registry.register_instance(
        instance,
        is_builtin=False,
        slug=slug,
        name=name,
        description=description,
    )


def _resolve_ssh_key(ctx, ssh_key_id: int | None) -> Any:
    db = ctx.db
    if ssh_key_id:
        key = db.ssh_keys.get(ssh_key_id)
    else:
        key = db.ssh_keys.default()
    if not key:
        raise ValueError("SSH-ключ не найден")
    return key


async def _provision_ssh_key(
    ctx,
    username: str,
    address: str,
    port: int,
    password: str,
    ssh_key_id: int | None = None,
) -> None:
    """Копирует выбранный SSH-ключ на удалённый хост через ssh-copy-id с паролем."""
    key = _resolve_ssh_key(ctx, ssh_key_id)
    public_key_path = key.public_key_path
    if not public_key_path:
        raise ValueError("У выбранного SSH-ключа нет публичной части")
    public_key = Path(public_key_path)
    if not public_key.exists():
        raise ValueError(f"Публичный ключ не найден: {public_key_path}")

    ssh_dir = Path.home() / ".ssh"
    ssh_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Pass the provisioning password via the SSHPASS environment variable so it
    # does not appear in the sshpass command line.
    env = {
        **os.environ,
        "HOME": str(Path.home()),
        "TMPDIR": "/tmp",
        "SSHPASS": password,
    }

    # Add the remote host key to known_hosts before attempting ssh-copy-id so
    # StrictHostKeyChecking=yes does not reject the connection.
    from computer.module.executor_ssh import SSH_KNOWN_HOSTS_FILE
    known_hosts_path = SSH_KNOWN_HOSTS_FILE or str(Path.home() / ".ssh" / "known_hosts")
    known_hosts_file = Path(known_hosts_path)
    known_hosts_file.parent.mkdir(parents=True, exist_ok=True)
    known_hosts_file.touch(mode=0o600, exist_ok=True)
    try:
        scan_result = await asyncio.to_thread(
            subprocess.run,
            ["ssh-keyscan", "-H", "-p", str(port), address],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if scan_result.stdout.strip():
            with known_hosts_file.open("a") as kh:
                kh.write(scan_result.stdout)
    except Exception:
        pass  # keyscan failure is non-fatal; ssh-copy-id will report auth error

    # Build ssh-copy-id options manually: BatchMode=yes must be omitted so
    # sshpass can inject the password; StrictHostKeyChecking is safe because
    # we just ran ssh-keyscan above.
    copy_id_opts = [
        "-o", "ConnectTimeout=10",
        "-o", "StrictHostKeyChecking=yes",
        "-o", "LogLevel=ERROR",
        "-o", f"UserKnownHostsFile={known_hosts_path}",
    ]
    cmd = [
        "sshpass",
        "-e",
        "ssh-copy-id",
        "-i",
        str(public_key),
        "-p",
        str(port),
        *copy_id_opts,
        f"{username}@{address}",
    ]
    try:
        result = await asyncio.to_thread(
            subprocess.run,
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
            env=env,
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        raise RuntimeError(f"ssh-copy-id не удалось: {stderr or exc.returncode}") from exc
    except FileNotFoundError as exc:
        raise RuntimeError("Утилита sshpass не установлена") from exc


def _save_ssh_key(name: str, file_data: str) -> Path:
    """Decode base64 key contents and store under /app/keys (or keys/ for non-Docker)."""
    keys_dir = Path("/app/keys")
    if not keys_dir.exists() or not keys_dir.is_dir():
        keys_dir = Path("keys")

    keys_dir.mkdir(parents=True, exist_ok=True)

    base_name = Path(name).name
    if not base_name or base_name in (".", ".."):
        base_name = "uploaded_key"
    target_path = keys_dir / base_name

    counter = 1
    original_path = target_path
    while target_path.exists():
        stem = original_path.stem
        suffix = original_path.suffix
        target_path = original_path.with_name(f"{stem}_{counter}{suffix}")
        counter += 1

    raw = base64.b64decode(file_data)
    target_path.write_bytes(raw)
    target_path.chmod(0o600)
    return target_path


def _generate_ssh_key(
    key_type: str, passphrase: str | None = None
) -> tuple[str, str, str, int]:
    """Generate an SSH key pair and return private PEM, public OpenSSH line, fingerprint and passphrase flag."""
    if key_type == "ed25519":
        private_key = ed25519.Ed25519PrivateKey.generate()
    elif key_type == "rsa":
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    else:
        raise ValueError(f"Unsupported key type: {key_type}")

    if passphrase:
        encryption = BestAvailableEncryption(passphrase.encode("utf-8"))
        has_passphrase = 1
    else:
        encryption = NoEncryption()
        has_passphrase = 0

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.OpenSSH,
        encryption_algorithm=encryption,
    ).decode("utf-8")

    public_key = private_key.public_key()
    public_openssh = public_key.public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH,
    ).decode("utf-8")

    fingerprint = _ssh_fingerprint(public_openssh)
    return private_pem, public_openssh, fingerprint, has_passphrase


def _write_generated_ssh_key(
    name: str, private_pem: str, public_openssh: str
) -> tuple[Path, Path]:
    """Store a generated key pair under /app/keys (or keys/ for non-Docker)."""
    keys_dir = Path("/app/keys")
    if not keys_dir.exists() or not keys_dir.is_dir():
        keys_dir = Path("keys")

    keys_dir.mkdir(parents=True, exist_ok=True)

    safe_name = re.sub(r"[^a-zA-Z0-9_.-]+", "_", name).strip("_.")
    if not safe_name:
        safe_name = "generated_key"
    private_path = keys_dir / safe_name

    counter = 1
    original_path = private_path
    while private_path.exists():
        stem = original_path.stem
        suffix = original_path.suffix
        private_path = original_path.with_name(f"{stem}_{counter}{suffix}")
        counter += 1

    public_path = private_path.with_suffix(".pub")
    private_path.write_text(private_pem, encoding="utf-8")
    private_path.chmod(0o600)
    public_path.write_text(public_openssh + "\n", encoding="utf-8")
    public_path.chmod(0o644)
    return private_path, public_path


def _ssh_fingerprint(public_openssh: str) -> str:
    """Return an OpenSSH-style SHA256 fingerprint for a public key line."""
    parts = public_openssh.split()
    if len(parts) < 2:
        return ""
    blob = base64.b64decode(parts[1])
    digest = hashlib.sha256(blob).digest()
    return "SHA256:" + base64.b64encode(digest).rstrip(b"=").decode("ascii")


# ---------------------------------------------------------------------------
# Error handling middleware
# ---------------------------------------------------------------------------

@web.middleware
async def error_middleware(request: web.Request, handler):
    try:
        response = await handler(request)
        return response
    except web.HTTPException as exc:
        # Return JSON for every HTTP error so the JS frontend can parse it.
        error_text = exc.text or exc.reason or "HTTP error"
        try:
            # If the exception already carried a JSON body, reuse its message.
            payload = json.loads(error_text)
            if isinstance(payload, dict) and "ok" in payload:
                return _json_response(payload, status=exc.status)
        except Exception:
            pass
        return _json_response({"ok": False, "error": error_text}, status=exc.status)
    except Exception as exc:
        logger.exception("Unhandled API error: %s", exc)
        return _json_response({"ok": False, "error": "Internal server error"}, status=500)


# ---------------------------------------------------------------------------
# Application setup and server entry point
# ---------------------------------------------------------------------------

# ── Scenarios API ───────────────────────────────────────────────────────


async def api_scenarios_list(request: web.Request) -> web.Response:
    db = _ctx(request).db
    scenarios = []
    for sc in db.scenarios.all():
        item = model_to_dict(sc)
        item["steps"] = db.scenario_steps.by_scenario(sc.id)
        item["step_count"] = len(item["steps"])
        item["run_count"] = len(db.scenario_runs.by_scenario(sc.id))
        scenarios.append(item)
    return _ok(scenarios)


async def api_scenarios_runs(request: web.Request) -> web.Response:
    db = _ctx(request).db
    runs = db.scenario_runs.all(order_by="id DESC")
    query = request.query
    limit = _safe_int(query.get("limit", 50), 50)
    result = []
    for r in runs[:limit]:
        item = model_to_dict(r)
        sc = db.scenarios.get(r.scenario_id)
        item["scenario_name"] = sc.name if sc else f"#{r.scenario_id}"
        step_runs = db.scenario_step_runs.by_run(r.id)
        item["step_runs"] = step_runs
        result.append(item)
    return _ok(result)


async def api_scenarios_create(request: web.Request) -> web.Response:
    db = _ctx(request).db
    payload = await _read_json(request)
    now = utcnow_iso()
    sc = db.scenarios.create(
        name=str(payload.get("name", "")).strip(),
        description=str(payload.get("description", "")).strip() or None,
        target_type="group",
        created_at=now,
        updated_at=now,
    )
    steps_data = payload.get("steps", [])
    for i, step_data in enumerate(steps_data, start=1):
        db.scenario_steps.create(
            scenario_id=sc.id,
            module_id=_safe_int(step_data.get("module_id")),
            step_order=i,
            step_name=str(step_data.get("step_name", f"Шаг {i}")).strip(),
            config_json=json.dumps(step_data.get("config", {}), ensure_ascii=False),
            on_failure=str(step_data.get("on_failure", "stop")).strip(),
            created_at=now,
        )
    return _ok(sc)


async def api_scenarios_run(request: web.Request) -> web.Response:
    """Запускает сценарий в фоне и сразу возвращает run_id для опроса прогресса."""
    ctx = _ctx(request)
    payload = await _read_json(request)
    scenario_id = _safe_int(payload.get("scenario_id"))
    target_type = str(payload.get("target_type", "group")).strip()
    target_id = _safe_int(payload.get("target_id"))

    # Создаём run-строку заранее, чтобы вернуть run_id немедленно.
    run = ctx.db.scenario_runs.start(
        scenario_id=scenario_id,
        target_type=target_type,
        target_id=target_id,
        trigger_type="manual",
    )

    async def _bg():
        try:
            await ctx.scenario_runner.run_scenario_async(
                scenario_id=scenario_id,
                target_type=target_type,
                target_id=target_id,
                trigger_type="manual",
                scenario_run_id=run.id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Scenario run %s failed: %s", run.id, exc)
            try:
                ctx.db.scenario_runs.finish(run.id, status="failed")
            except Exception:
                pass

    await _run_background(request.app, _bg())
    return _ok({"run_id": run.id, "status": run.status})


async def api_scenarios_run_status(request: web.Request) -> web.Response:
    """Статус одного запуска сценария + его step_runs (для живого опроса)."""
    ctx = _ctx(request)
    run_id = _safe_int(request.match_info["id"])
    run = ctx.db.scenario_runs.get(run_id)
    if run is None:
        return _error("Scenario run not found", status=404)
    item = model_to_dict(run)
    sc = ctx.db.scenarios.get(run.scenario_id)
    item["scenario_name"] = sc.name if sc else f"#{run.scenario_id}"
    item["step_runs"] = ctx.db.scenario_step_runs.by_run(run_id)
    return _ok(item)


async def api_scenarios_delete(request: web.Request) -> web.Response:
    db = _ctx(request).db
    payload = await _read_json(request)
    scenario_id = _safe_int(payload.get("id"))
    db.scenarios.delete(scenario_id)
    return _ok({"deleted": scenario_id})


def _build_app(app_context) -> web.Application:
    app = web.Application(middlewares=[auth_middleware, error_middleware])
    app["ctx"] = app_context
    app["auth_service"] = AuthService(app_context.db)
    app["websockets"] = set()
    app["background_tasks"] = set()

    # Public authentication endpoints
    app.router.add_post("/api/login", api_login)
    app.router.add_post("/api/login/verify", api_login_verify)
    app.router.add_post("/api/register", api_register)
    app.router.add_post("/api/logout", api_logout)
    app.router.add_get("/api/me", api_me)
    app.router.add_post("/api/me/update", api_me_update)

    # Health check (public, used by the supervisor)
    app.router.add_get("/healthz", healthz_handler)

    # Static files
    app.router.add_get("/", index_handler)
    app.router.add_static("/static", STATIC_DIR)
    app.router.add_get("/reports/{path:.*}", reports_handler)

    # API GET
    app.router.add_get("/api/summary", api_summary)
    app.router.add_get("/api/hosts", api_hosts)
    app.router.add_get("/api/groups", api_groups)
    app.router.add_get("/api/modules", api_modules)
    app.router.add_get("/api/task-templates", api_task_templates)
    app.router.add_get("/api/task-runs", api_task_runs)
    app.router.add_get("/api/run/{id}/status", api_task_run_status)
    app.router.add_get("/api/inventory", api_inventory)
    app.router.add_get("/api/scheduled", api_scheduled)
    app.router.add_get("/api/reports", api_reports)
    app.router.add_get("/api/system-logs", api_system_logs)
    app.router.add_get("/api/ssh-keys", api_ssh_keys)

    # API POST
    app.router.add_post("/api/hosts", api_hosts_create)
    app.router.add_post("/api/hosts/update", api_hosts_update)
    app.router.add_post("/api/hosts/delete", api_hosts_delete)
    app.router.add_post("/api/hosts/check", api_hosts_check)
    app.router.add_post("/api/hosts/check-all", api_hosts_check_all)
    app.router.add_post("/api/hosts/reprovision", api_hosts_reprovision)
    app.router.add_get("/api/uploads", api_uploads_list)
    app.router.add_post("/api/uploads", api_uploads_create)
    app.router.add_get("/api/uploads/{id}/download", api_uploads_download)
    app.router.add_post("/api/uploads/delete", api_uploads_delete)
    app.router.add_post("/api/groups", api_groups_create)
    app.router.add_post("/api/groups/update", api_groups_update)
    app.router.add_post("/api/groups/delete", api_groups_delete)
    app.router.add_post("/api/groups/add-host", api_groups_add_host)
    app.router.add_post("/api/run", api_run)
    app.router.add_post("/api/run/{id}/cancel", api_run_cancel)
    app.router.add_post("/api/modules", api_modules_create)
    app.router.add_post("/api/modules/update", api_modules_update)
    app.router.add_post("/api/modules/delete", api_modules_delete)
    app.router.add_post("/api/schedule", api_schedule_create)
    app.router.add_post("/api/schedule/update", api_schedule_update)
    app.router.add_post("/api/schedule/delete", api_schedule_delete)
    app.router.add_post("/api/scheduler/tick", api_scheduler_tick)
    app.router.add_post("/api/task-runs/clear", api_task_runs_clear)
    app.router.add_post("/api/reports/clear", api_reports_clear)
    app.router.add_post("/api/reports/export", api_reports_export)
    app.router.add_post("/api/ssh-keys", api_ssh_keys_create)
    app.router.add_post("/api/keys/generate", api_keys_generate)

    # Admin API
    app.router.add_get("/api/admin/users", api_admin_users_list)
    app.router.add_post("/api/admin/users", api_admin_users_create)
    app.router.add_post("/api/admin/users/update", api_admin_users_update)
    app.router.add_post("/api/admin/users/delete", api_admin_users_delete)
    app.router.add_get("/api/admin/user-modules", api_admin_user_modules)
    app.router.add_post("/api/admin/user-modules", api_admin_user_modules_set)
    app.router.add_get("/api/admin/user-groups", api_admin_user_groups)
    app.router.add_post("/api/admin/user-groups", api_admin_user_groups_set)
    app.router.add_get("/api/admin/db-tables", api_admin_db_tables)
    app.router.add_get("/api/admin/backup", api_admin_backup)
    app.router.add_post("/api/admin/restore", api_admin_restore)
    app.router.add_get("/api/admin/host-agents", api_admin_host_agents)
    app.router.add_get("/api/admin/host-events", api_admin_host_events)

    # Boards API
    app.router.add_get("/api/boards", api_boards_list)
    app.router.add_post("/api/boards", api_boards_create)
    app.router.add_get("/api/boards/{id}", api_boards_get)
    app.router.add_post("/api/boards/{id}", api_boards_update)
    app.router.add_post("/api/boards/{id}/delete", api_boards_delete)
    app.router.add_post("/api/boards/{id}/layout", api_boards_save_layout)

    # Scenarios API
    app.router.add_get("/api/scenarios", api_scenarios_list)
    app.router.add_get("/api/scenarios/runs", api_scenarios_runs)
    app.router.add_get("/api/scenarios/runs/{id}", api_scenarios_run_status)
    app.router.add_post("/api/scenarios", api_scenarios_create)
    app.router.add_post("/api/scenarios/run", api_scenarios_run)
    app.router.add_post("/api/scenarios/delete", api_scenarios_delete)

    # Update API
    app.router.add_get("/api/update/check", api_update_check)
    app.router.add_get("/api/update/diff", api_update_diff)
    app.router.add_post("/api/update/pull", api_update_pull)
    app.router.add_get("/api/update/status", api_update_status)
    app.router.add_post("/api/update/recheck", api_update_recheck)
    app.router.add_post("/api/update/config", api_update_set_config)
    app.router.add_post("/api/update/apply", api_update_apply)
    app.router.add_get("/api/update/incidents", api_update_incidents)
    app.router.add_get("/api/me/telegram/status", api_me_telegram_status)
    app.router.add_post("/api/me/telegram/link", api_me_telegram_link)
    app.router.add_post("/api/me/telegram/unlink", api_me_telegram_unlink)
    app.router.add_get("/api/me/devices", api_me_devices_list)
    app.router.add_post("/api/me/devices/trust", api_me_devices_trust)
    app.router.add_post("/api/me/devices/revoke", api_me_devices_revoke)
    app.router.add_get("/api/admin/telegram", api_admin_telegram_get)
    app.router.add_post("/api/admin/telegram", api_admin_telegram_set)

    # WebSocket
    app.router.add_get("/ws", websocket_handler)
    app.router.add_get("/agent/ws", agent_websocket_handler)
    app.router.add_get("/api/terminal/ws", api_terminal_ws)

    return app



async def api_update_check(request: web.Request) -> web.Response:
    """Проверить наличие обновлений через git."""
    RUNNER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        result = subprocess.run(
            ["git", "fetch"],
            cwd=RUNNER_DIR, capture_output=True, text=True, timeout=30
        )
        result2 = subprocess.run(
            ["git", "rev-list", "--count", "HEAD..@{u}"],
            cwd=RUNNER_DIR, capture_output=True, text=True, timeout=15
        )
        behind = result2.stdout.strip()
        if behind and behind.isdigit() and int(behind) > 0:
            log = subprocess.run(
                ["git", "--no-pager", "log", "-1", "@{u}", "--pretty=%B"],
                cwd=RUNNER_DIR, capture_output=True, text=True, timeout=15
            )
            diff = subprocess.run(
                ["git", "diff", "--stat", "HEAD..@{u}"],
                cwd=RUNNER_DIR, capture_output=True, text=True, timeout=15
            )
            return _ok({
                "behind": int(behind),
                "last_message": log.stdout.strip()[:500],
                "diff_stats": diff.stdout.strip()[:2000],
                "has_upstream": True,
            })
        elif behind and behind.isdigit() and int(behind) == 0:
            return _ok({"behind": 0, "has_upstream": True, "message": "Всё актуально"})
        else:
            return _ok({"has_upstream": False, "message": "Нет upstream-ветки. Репа без пулла."})
    except subprocess.TimeoutExpired:
        return _ok({"error": "Таймаут git fetch"})
    except Exception as e:
        return _ok({"error": str(e)[:200]})


async def api_update_diff(request: web.Request) -> web.Response:
    """Показать diff того, что изменится."""
    RUNNER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        subprocess.run(["git", "fetch"], cwd=RUNNER_DIR, capture_output=True, text=True, timeout=30)
        result = subprocess.run(
            ["git", "diff", "HEAD..@{u}", "--stat"],
            cwd=RUNNER_DIR, capture_output=True, text=True, timeout=15
        )
        result2 = subprocess.run(
            ["git", "diff", "HEAD..@{u}", "-p", "--", "*.py", "*.ts", "*.tsx", "*.json", "*.sh", "Dockerfile", "*.yml"],
            cwd=RUNNER_DIR, capture_output=True, text=True, timeout=15
        )
        changed_files = subprocess.run(
            ["git", "diff", "--name-only", "HEAD..@{u}"],
            cwd=RUNNER_DIR, capture_output=True, text=True, timeout=15
        )
        return _ok({
            "stat": result.stdout.strip()[:3000],
            "diff": result2.stdout.strip()[:15000],
            "files": changed_files.stdout.strip()[:2000],
        })
    except Exception as e:
        return _ok({"error": str(e)[:200]})


async def api_update_pull(request: web.Request) -> web.Response:
    """Применить обновления (git pull)."""
    RUNNER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        result = subprocess.run(
            ["git", "pull"],
            cwd=RUNNER_DIR, capture_output=True, text=True, timeout=60
        )
        return _ok({
            "stdout": result.stdout.strip()[:1000],
            "stderr": result.stderr.strip()[:500],
            "returncode": result.returncode,
        })
    except subprocess.TimeoutExpired:
        return _ok({"error": "Таймаут git pull"})
    except Exception as e:
        return _ok({"error": str(e)[:200]})


async def _update_monitor(app: web.Application):
    """Фоновый монитор git: периодически проверяет наличие обновлений (режим «уведомлять»).

    Интервал и факт настройки репозитория читаются из конфига. Сетевые git-операции
    выполняются в отдельном потоке со своим соединением БД (sqlite не потокобезопасен).
    """
    db_path = app["ctx"].db_path

    def _work():
        db = open_database(db_path)
        try:
            svc = UpdateService(db)
            cfg = svc.get_config()
            interval = cfg.get("poll_interval", 600)
            result = svc.check() if cfg.get("remote") else None
            return interval, result
        finally:
            db.close()

    while True:
        interval = 600
        try:
            interval, result = await asyncio.to_thread(_work)
            if result is not None:
                result["checked_at"] = utcnow_iso()
                app["update_status"] = result
        except asyncio.CancelledError:
            break
        except Exception as exc:  # noqa: BLE001
            logger.warning("Update monitor failed: %s", exc)
        try:
            await asyncio.sleep(max(60, interval))
        except asyncio.CancelledError:
            break


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


async def _periodic_ping(app: web.Application, interval: int):
    """Background daemon: periodically check all hosts using a fresh DB connection."""
    db_path = app["ctx"].db_path
    while True:
        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            break
        try:
            db = open_database(db_path)
            try:
                host_service = HostService(db)
                await host_service.check_all_hosts_async()
            finally:
                db.close()
        except Exception as _ping_exc:
            logger.warning("Periodic host ping failed: %s", _ping_exc)


def run_web_server(
    app_context,
    host: str = "127.0.0.1",
    port: int = 8000,
    open_browser: bool = False,
    ping_interval: int = 60,
) -> None:
    """Запускает локальную async web-панель NetRunner."""

    app = _build_app(app_context)

    async def _on_startup(_app):
        _app["auth_service"].create_default_user()
        if ping_interval > 0:
            ping_task = asyncio.create_task(_periodic_ping(_app, ping_interval))
            _app["ping_task"] = ping_task
        _app["update_task"] = asyncio.create_task(_update_monitor(_app))
        _app["telegram_task"] = asyncio.create_task(_telegram_poller(_app))

    async def _on_cleanup(_app):
        for _key in ("ping_task", "update_task", "telegram_task"):
            if _key in _app:
                _app[_key].cancel()
                try:
                    await _app[_key]
                except asyncio.CancelledError:
                    pass
        for task in list(_app["background_tasks"]):
            task.cancel()
        await asyncio.gather(*_app["background_tasks"], return_exceptions=True)
        for ws in list(_app["websockets"]):
            await ws.close()

    app.on_startup.append(_on_startup)
    app.on_cleanup.append(_on_cleanup)

    url = f"http://{host}:{port}/"
    print(f"NetRunner web-GUI запущен: {url}")
    print("Для остановки нажмите Ctrl+C")

    if open_browser:
        webbrowser.open(url)

    web.run_app(app, host=host, port=port)
