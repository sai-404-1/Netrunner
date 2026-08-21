from aiohttp import web
import json

from server.domens.websocket import _broadcast_task_update
from server.tools import _ctx, _ok, model_to_dict, _safe_int, _error, _read_json
from services.host_service import _run_background

from services.logger import Logger

logger = Logger()

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


async def api_task_runs_clear(request: web.Request) -> web.Response:
    ctx = _ctx(request)
    await _read_json(request)
    ctx.db.task_runs.clear_all()
    return _ok({"cleared": True})