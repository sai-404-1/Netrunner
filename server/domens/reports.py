from aiohttp import web

from server.tools import _ok, _ctx, _read_json, _safe_int, model_to_dict, _error


async def api_reports(request: web.Request) -> web.Response:
    report_type = request.query.get("type")
    return _ok(_ctx(request).db.reports.latest(50, report_type=report_type))


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