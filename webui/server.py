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
from webui.auth_handlers import api_login, api_logout, api_me, api_register
from webui.auth_middleware import auth_middleware


STATIC_DIR = Path(__file__).resolve().parent / "static"
logger = logging.getLogger("netrunner")


def model_to_dict(value: Any) -> Any:
    """Преобразует dataclass-модели, списки и словари в JSON-совместимый вид."""

    if value is None:
        return None
    if is_dataclass(value):
        return asdict(value)
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

async def index_handler(request: web.Request) -> web.Response:
    return web.FileResponse(STATIC_DIR / "index.html")


async def reports_handler(request: web.Request) -> web.Response:
    report_path = request.match_info["path"]
    reports_dir = Path(_ctx(request).reports_dir).resolve()
    target = (reports_dir / report_path).resolve()
    if not str(target).startswith(str(reports_dir)):
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
    data = {
        "hosts": len(db.hosts.all()),
        "groups": len(db.groups.all()),
        "modules": len(db.modules.all()),
        "task_runs": len(db.task_runs.all()),
        "inventory": len(inventory),
        "scheduled": len(db.scheduled.all()),
        "reports": len(db.reports.all()),
        "recent_task_runs": task_runs,
        "latest_inventory": inventory[:5],
        "latest_reports": reports,
    }
    return _ok(data)


async def api_hosts(request: web.Request) -> web.Response:
    db = _ctx(request).db
    hosts = []
    for host in db.hosts.all():
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
    modules = []
    runtime_modules = {item.slug: item for item in _ctx(request).module_registry.all()}
    for row in db.modules.all():
        item = model_to_dict(row)
        runtime = runtime_modules.get(row.slug)
        item["supports_task_runner"] = bool(runtime and runtime.supports_task_runner)
        item["web_ui_visible"] = getattr(runtime, "web_ui_visible", True) if runtime else True
        modules.append(item)
    return _ok(modules)


async def api_task_templates(request: web.Request) -> web.Response:
    return _ok(_ctx(request).db.task_templates.all())


async def api_task_runs(request: web.Request) -> web.Response:
    limit = _safe_int(request.query.get("limit", 50), 50)
    return _ok(_ctx(request).db.task_runs.list_recent(limit))


async def api_task_run_status(request: web.Request) -> web.Response:
    run_id = _safe_int(request.match_info["id"])
    run = _ctx(request).db.task_runs.get(run_id)
    if run is None:
        return _error("Task run not found", status=404)
    return _ok(model_to_dict(run))


async def api_inventory(request: web.Request) -> web.Response:
    return _ok(_ctx(request).db.inventory.all(order_by="collected_at DESC"))


async def api_scheduled(request: web.Request) -> web.Response:
    return _ok(_ctx(request).db.scheduled.all())


async def api_reports(request: web.Request) -> web.Response:
    report_type = request.query.get("type")
    return _ok(_ctx(request).db.reports.latest(50, report_type=report_type))


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
    )
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


async def api_groups_create(request: web.Request) -> web.Response:
    ctx = _ctx(request)
    payload = await _read_json(request)
    group = ctx.host_service.create_group(
        name=str(payload.get("name") or "").strip(),
        kind=str(payload.get("kind") or "custom").strip() or "custom",
        description=str(payload.get("description") or "").strip() or None,
    )
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

    module = ctx.db.modules.create(
        name=name,
        slug=slug,
        module_path=module_path,
        class_name=class_name,
        is_builtin=0,
        is_enabled=1,
        description=description,
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
    scheduled = ctx.db.scheduled.create(
        name=str(payload.get("name") or "").strip(),
        template_id=_safe_int(payload.get("template_id")),
        target_type=str(payload.get("target_type") or "host").strip(),
        target_id=_safe_int(payload.get("target_id")),
        run_at=str(payload.get("run_at") or "").strip(),
        is_enabled=1 if payload.get("is_enabled", True) else 0,
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
    cmd = [
        "sshpass",
        "-e",
        "ssh-copy-id",
        "-i",
        str(public_key),
        "-p",
        str(port),
        *_ssh_common_options(),
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
        return _json_response(
            {"ok": False, "error": str(exc), "traceback": traceback.format_exc()},
            status=500,
        )


# ---------------------------------------------------------------------------
# Application setup and server entry point
# ---------------------------------------------------------------------------

def _build_app(app_context) -> web.Application:
    app = web.Application(middlewares=[auth_middleware, error_middleware])
    app["ctx"] = app_context
    app["auth_service"] = AuthService(app_context.db)
    app["websockets"] = set()
    app["background_tasks"] = set()

    # Public authentication endpoints
    app.router.add_post("/api/login", api_login)
    app.router.add_post("/api/register", api_register)
    app.router.add_post("/api/logout", api_logout)
    app.router.add_get("/api/me", api_me)

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
    app.router.add_get("/api/ssh-keys", api_ssh_keys)

    # API POST
    app.router.add_post("/api/hosts", api_hosts_create)
    app.router.add_post("/api/hosts/update", api_hosts_update)
    app.router.add_post("/api/hosts/delete", api_hosts_delete)
    app.router.add_post("/api/hosts/check", api_hosts_check)
    app.router.add_post("/api/hosts/check-all", api_hosts_check_all)
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

    # WebSocket
    app.router.add_get("/ws", websocket_handler)

    return app


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
        except Exception:
            pass


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
        if ping_interval > 0:
            ping_task = asyncio.create_task(_periodic_ping(_app, ping_interval))
            _app["ping_task"] = ping_task

    async def _on_cleanup(_app):
        if "ping_task" in _app:
            _app["ping_task"].cancel()
            try:
                await _app["ping_task"]
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
