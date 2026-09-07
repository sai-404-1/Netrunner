from aiohttp import web

from server.tools import _ok, _ctx, _read_json, _safe_int


async def api_scheduled(request: web.Request) -> web.Response:
    return _ok(_ctx(request).db.scheduled.all())


async def api_active_scheduled(request: web.Request) -> web.Response:
    return _ok(_ctx(request).db.scheduled.filter(is_enabled=True))


async def api_inactive_scheduled(request: web.Request) -> web.Response:
    return _ok(_ctx(request).db.scheduled.filter(is_enabled=False))


async def api_schedule_create(request: web.Request) -> web.Response:
    ctx = _ctx(request)
    payload = await _read_json(request)
    run_at = str(payload.get("run_at") or "").strip()
    if not run_at:
        raise web.HTTPBadRequest(reason="run_at is required")
    scenario_id = _safe_int(payload.get("scenario_id"))
    if not scenario_id:
        raise web.HTTPBadRequest(reason="scenario_id is required")
    interval_raw = payload.get("interval_seconds")
    max_runs_raw = payload.get("max_runs")
    wait_for_online = payload.get("wait_for_online")
    scheduled = ctx.db.scheduled.create(
        name=str(payload.get("name") or "").strip(),
        scenario_id=scenario_id,
        target_type=str(payload.get("target_type") or "host").strip(),
        target_id=_safe_int(payload.get("target_id")),
        run_at=run_at,
        is_enabled=1 if payload.get("is_enabled", True) else 0,
        wait_for_online=1 if wait_for_online else 0,

        # TODO проверить что из-за None нет последствий и найти причину по которой возможен None
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
    if "scenario_id" in updates:
        updates["scenario_id"] = _safe_int(updates["scenario_id"])
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