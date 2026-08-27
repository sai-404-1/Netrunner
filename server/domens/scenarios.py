import json

from aiohttp import web

from database.models import BaseModel
from database.repos import utcnow_iso
from server.tools import model_to_dict, _safe_int, _ctx, _ok, _read_json, _error
from services.host_service import _run_background
from services.logger import Logger

logger = Logger()


def _apply_scenario_steps(db, scenario_id: int, steps_data: list, now: str) -> None:
    """Пересоздаёт шаги сценария: чистит старые, пишет новые (порядок = step_order).

    TODO(будущее): пересоздание шагов каскадно стирает scenario_step_runs уже
    прошедших запусков (FK step_id ON DELETE CASCADE) и меняет конфиг, на который
    могли ссылаться идущие запуски. Риск: если сценарий редактируют во время
    запуска, исполнитель получает неожиданный результат. План: два доп. столбца
    у scenarios (is_locked / is_running): блокировать редактирование, пока
    сценарий запущен, и блокировать запуск, пока сценарий редактируется.
    """
    for old in db.scenario_steps.by_scenario(scenario_id):
        db.scenario_steps.delete(old.id)
    for i, step_data in enumerate(steps_data, start=1):
        db.scenario_steps.create(
            scenario_id=scenario_id,
            module_id=_safe_int(step_data.get("module_id")),
            step_order=i,
            step_name=str(step_data.get("step_name", f"Шаг {i}")).strip(),
            config_json=json.dumps(step_data.get("config", {}), ensure_ascii=False),
            on_failure=str(step_data.get("on_failure", "stop")).strip(),
            created_at=now,
        )

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
    _apply_scenario_steps(db, sc.id, steps_data, now)
    return _ok(sc)

async def api_scenarios_update(request: web.Request) -> web.Response:
    """Обновляет сценарий: название, описание и шаги (пересоздаёт порядок модулей)."""
    db = _ctx(request).db
    payload = await _read_json(request)
    scenario_id = _safe_int(payload.get("scenario_id"))
    now = utcnow_iso()

    sc = db.scenarios.get(scenario_id)
    if sc is None:
        return _error("Сценарий не найден", status=404)

    db.scenarios.update(
        scenario_id,
        name=str(payload.get("name", sc.name)).strip(),
        description=str(payload.get("description", "")).strip() or None,
        updated_at=now,
    )
    _apply_scenario_steps(db, scenario_id, payload.get("steps", []), now)
    return _ok({"updated": scenario_id})


async def api_scenarios_run(request: web.Request) -> web.Response:
    """Запускает один или несколько сценариев в фоне и сразу возвращает run_id(s).

    Один сценарий: `{"scenario_id": N, "target_type": ..., "target_id": ...}`.
    Несколько (последовательно, по очереди): `{"scenario_ids": [N1, N2], ...}`.
    """
    ctx = _ctx(request)
    payload = await _read_json(request)
    target_type = str(payload.get("target_type", "group")).strip()
    target_id = _safe_int(payload.get("target_id"))

    ids = payload.get("scenario_ids") or []
    if isinstance(ids, (list, tuple)):
        scenario_ids = [_safe_int(x) for x in ids]
    else:
        scenario_ids = [_safe_int(payload.get("scenario_id"))]
    scenario_ids = [s for s in scenario_ids if s]

    if not scenario_ids:
        return _error("Не указан сценарий", status=400)

    # Создаём run-строки заранее, чтобы вернуть run_id(s) немедленно.
    runs = [
        ctx.db.scenario_runs.start(
            scenario_id=sid, target_type=target_type, target_id=target_id, trigger_type="manual",
        )
        for sid in scenario_ids
    ]
    run_ids = [r.id for r in runs]

    async def _bg() -> None:
        # Выполняем сценарии строго по очереди (каждый ждёт завершения предыдущего).
        for sid, run in zip(scenario_ids, runs):
            try:
                await ctx.scenario_runner.run_scenario_async(
                    scenario_id=sid,
                    target_type=target_type,
                    target_id=target_id,
                    trigger_type="manual",
                    scenario_run_id=run.id,
                )
            except Exception:  # noqa: BLE001
                logger.exception("Ошибка при выполнении сценария %s", run.id)
                try:
                    ctx.db.scenario_runs.finish(run.id, status="failed")
                except Exception:  # noqa: BLE001
                    logger.error("Не удалось пометить run %s как failed", run.id)

    await _run_background(request.app, _bg())
    return _ok({"run_ids": run_ids, "run_id": run_ids[0] if run_ids else None, "status": runs[0].status})


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