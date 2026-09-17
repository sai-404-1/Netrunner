import json

from aiohttp import web

from database.models import BaseModel
from database.repos import utcnow_iso
from server.tools import model_to_dict, _safe_int, _ctx, _ok, _read_json, _error, \
    is_teacher, allowed_host_ids, allowed_group_ids
from services.host_service import _run_background
from services.logger import Logger

logger = Logger()


def _admin_only_module_name(ctx, module_id: int) -> str | None:
    """Имя модуля, если он admin_only, иначе None."""
    module_row = ctx.db.modules.get(module_id)
    if not module_row:
        return None
    try:
        runtime = ctx.module_registry.get(module_row.slug)
    except KeyError:
        return None
    if getattr(runtime.instance, "admin_only", False):
        return module_row.name or module_row.slug
    return None


def _scenario_admin_only_step(ctx, scenario_id: int) -> str | None:
    """Имя admin_only-модуля среди УЖЕ СОХРАНЁННЫХ шагов сценария, иначе None.

    ScenarioRunner исполняет шаги напрямую, минуя ту же проверку admin_only,
    что /api/run делает для одиночного запуска (server/domens/tasks.py) —
    без этой проверки сценарий с шагом agent_provision/file_distribute
    запускал бы их от имени любой роли с доступом к странице сценариев
    (включая преподавателя, для которого оба модуля admin_only).
    """
    for step in ctx.db.scenario_steps.by_scenario(scenario_id):
        name = _admin_only_module_name(ctx, step.module_id)
        if name:
            return name
    return None


def _payload_admin_only_step(ctx, steps_data: list) -> str | None:
    """То же самое, но по шагам из тела запроса (для create/update — до записи
    в БД, чтобы преподаватель не мог даже сохранить такой шаг)."""
    for step in steps_data:
        name = _admin_only_module_name(ctx, _safe_int(step.get("module_id")))
        if name:
            return name
    return None


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

def _host_names(db) -> dict:
    return {h.id: h.name for h in db.hosts.all()}


def _step_runs_with_hosts(db, step_runs: list, names: dict | None = None) -> list:
    """step_run + имя хоста: в интерфейсе вывод разложен по вкладкам компьютеров,
    голый host_id там читать нечем."""
    names = names if names is not None else _host_names(db)
    result = []
    for sr in step_runs:
        item = model_to_dict(sr)
        item["host_name"] = names.get(sr.host_id, f"#{sr.host_id}")
        result.append(item)
    return result


def _run_hosts(ctx, run) -> list:
    """Хосты, на которых идёт запуск — нужны фронту, чтобы отрисовать вкладки
    сразу, ещё до появления первых step_run."""
    try:
        targets = ctx.host_service.resolve_targets(run.target_type, run.target_id)
    except Exception:  # noqa: BLE001
        return []
    return [{"id": h.id, "name": h.name} for h in targets]


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
    names = _host_names(db)
    result = []
    for r in runs[:limit]:
        item = model_to_dict(r)
        sc = db.scenarios.get(r.scenario_id)
        item["scenario_name"] = sc.name if sc else f"#{r.scenario_id}"
        item["step_runs"] = _step_runs_with_hosts(db, db.scenario_step_runs.by_run(r.id), names)
        result.append(item)
    return _ok(result)


async def api_scenarios_create(request: web.Request) -> web.Response:
    ctx = _ctx(request)
    db = ctx.db
    user = request.get("auth_user")
    payload = await _read_json(request)
    steps_data = payload.get("steps", [])
    if not (user and user.get("is_superuser")):
        blocked = _payload_admin_only_step(ctx, steps_data)
        if blocked:
            return _error(f"Шаг с модулем «{blocked}» доступен только администратору", status=403)
    now = utcnow_iso()
    sc = db.scenarios.create(
        name=str(payload.get("name", "")).strip(),
        description=str(payload.get("description", "")).strip() or None,
        target_type="group",
        folder_id=_safe_int(payload.get("folder_id")) or None,
        created_at=now,
        updated_at=now,
    )
    _apply_scenario_steps(db, sc.id, steps_data, now)
    return _ok(sc)

async def api_scenarios_update(request: web.Request) -> web.Response:
    """Обновляет сценарий: название, описание и шаги (пересоздаёт порядок модулей)."""
    ctx = _ctx(request)
    db = ctx.db
    user = request.get("auth_user")
    payload = await _read_json(request)
    scenario_id = _safe_int(payload.get("scenario_id"))
    steps_data = payload.get("steps", [])
    now = utcnow_iso()

    sc = db.scenarios.get(scenario_id)
    if sc is None:
        return _error("Сценарий не найден", status=404)
    if not (user and user.get("is_superuser")):
        blocked = _payload_admin_only_step(ctx, steps_data)
        if blocked:
            return _error(f"Шаг с модулем «{blocked}» доступен только администратору", status=403)

    db.scenarios.update(
        scenario_id,
        name=str(payload.get("name", sc.name)).strip(),
        description=str(payload.get("description", "")).strip() or None,
        updated_at=now,
    )
    _apply_scenario_steps(db, scenario_id, steps_data, now)
    return _ok({"updated": scenario_id})


async def api_scenarios_run(request: web.Request) -> web.Response:
    """Запускает один или несколько сценариев в фоне и сразу возвращает run_id(s).

    Один сценарий: `{"scenario_id": N, "target_type": ..., "target_id": ...}`.
    Несколько (последовательно, по очереди): `{"scenario_ids": [N1, N2], ...}`.
    Цель — либо одиночная (target_type/target_id), либо мультивыбор
    (host_ids + group_ids — смесь конкретных компов и кабинетов).
    """
    ctx = _ctx(request)
    user = request.get("auth_user")
    payload = await _read_json(request)
    target_type = str(payload.get("target_type", "group")).strip()
    target_id = _safe_int(payload.get("target_id"))
    host_ids = payload.get("host_ids")
    group_ids = payload.get("group_ids")
    is_multi = (isinstance(host_ids, list) and host_ids) or (isinstance(group_ids, list) and group_ids)

    if is_teacher(user):
        # Отказываем целиком, а не молча отфильтровываем чужие цели: иначе
        # запрос «весь кабинет + один посторонний хост» тихо выполнился бы без
        # этого хоста, и учитель не понял бы, что часть цели была отклонена.
        visible_hosts = allowed_host_ids(ctx.db, user) or set()
        visible_groups = allowed_group_ids(ctx.db, user) or set()
        req_host_ids = [_safe_int(x) for x in (host_ids or [])] if isinstance(host_ids, list) else []
        req_group_ids = [_safe_int(x) for x in (group_ids or [])] if isinstance(group_ids, list) else []
        if not is_multi:
            if target_type == "host":
                req_host_ids = [target_id]
            elif target_type == "group":
                req_group_ids = [target_id]
        if any(h not in visible_hosts for h in req_host_ids) or any(g not in visible_groups for g in req_group_ids):
            return _error("Цель вне ваших кабинетов", status=403)

    ids = payload.get("scenario_ids") or []
    if isinstance(ids, (list, tuple)):
        scenario_ids = [_safe_int(x) for x in ids]
    else:
        scenario_ids = [_safe_int(payload.get("scenario_id"))]
    scenario_ids = [s for s in scenario_ids if s]

    if not scenario_ids:
        return _error("Не указан сценарий", status=400)

    if not (user and user.get("is_superuser")):
        for sid in scenario_ids:
            blocked = _scenario_admin_only_step(ctx, sid)
            if blocked:
                return _error(f"Сценарий использует модуль «{blocked}», доступный только администратору", status=403)

    targets = None
    effective_target_type = target_type
    effective_target_id = target_id
    if is_multi:
        # Мультивыбор: раскрываем смесь кабинетов/компов в конкретный список хостов.
        targets = ctx.host_service.resolve_scheduled_targets(host_ids, group_ids)
        if targets:
            effective_target_type = "host"
            effective_target_id = targets[0].id  # совместимость истории/целей

    # Создаём run-строки заранее, чтобы вернуть run_id(s) немедленно.
    runs = [
        ctx.db.scenario_runs.start(
            scenario_id=sid,
            target_type=effective_target_type,
            target_id=effective_target_id,
            trigger_type="manual",
        )
        for sid in scenario_ids
    ]
    run_ids = [r.id for r in runs]

    async def _bg() -> None:
        # Очередь сценариев отдаётся раннеру целиком: он ведёт её пер-хост, так
        # что каждый компьютер идёт по своей очереди независимо от соседей.
        try:
            await ctx.scenario_runner.run_scenarios_async(
                scenario_ids=scenario_ids,
                target_type=effective_target_type,
                target_id=effective_target_id,
                trigger_type="manual",
                scenario_run_ids=run_ids,
                targets=targets,
            )
        except Exception:  # noqa: BLE001
            logger.exception("Ошибка при выполнении сценариев %s", run_ids)
            for run in runs:
                try:
                    if ctx.db.scenario_runs.get(run.id).status == "running":
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
    item["step_runs"] = _step_runs_with_hosts(ctx.db, ctx.db.scenario_step_runs.by_run(run_id))
    item["hosts"] = _run_hosts(ctx, run)
    return _ok(item)


async def api_scenarios_delete(request: web.Request) -> web.Response:
    # Фронт уже прячет кнопку удаления от учителя (CreateScenarioModal,
    # onDelete={isTeacher ? undefined : ...}) — эндпоинт эту границу не держал,
    # запрос напрямую удалял чужой сценарий с любой ролью.
    if is_teacher(request.get("auth_user")):
        return _error("Удаление сценариев доступно только администратору", status=403)
    db = _ctx(request).db
    payload = await _read_json(request)
    scenario_id = _safe_int(payload.get("id"))
    db.scenarios.delete(scenario_id)
    return _ok({"deleted": scenario_id})


# --------------------------------------------------------------------------
# Папки сценариев
#
# Читать папки может любой авторизованный пользователь (преподаватель видит
# ту же структуру, что и администратор) — а создавать, переименовывать,
# удалять и перекладывать сценарии может только суперпользователь.
# --------------------------------------------------------------------------

def _folders_admin_guard(request: web.Request):
    """None, если можно менять папки; иначе готовый ответ 403."""
    user = request.get("auth_user")
    if user and user.get("is_superuser"):
        return None
    return _error("Управление папками доступно только администратору", status=403)


async def api_scenario_folders_list(request: web.Request) -> web.Response:
    db = _ctx(request).db
    folders = []
    for folder in db.scenario_folders.all_sorted():
        item = model_to_dict(folder)
        item["scenario_count"] = len(db.scenarios.filter(folder_id=folder.id))
        folders.append(item)
    return _ok(folders)


async def api_scenario_folders_create(request: web.Request) -> web.Response:
    denied = _folders_admin_guard(request)
    if denied:
        return denied
    db = _ctx(request).db
    payload = await _read_json(request)
    name = str(payload.get("name") or "").strip()
    if not name:
        return _error("Укажите название папки")
    if db.scenario_folders.by_name(name):
        return _error(f"Папка «{name}» уже существует")
    now = utcnow_iso()
    folder = db.scenario_folders.create(name=name, created_at=now, updated_at=now)
    return _ok(folder)


async def api_scenario_folders_update(request: web.Request) -> web.Response:
    denied = _folders_admin_guard(request)
    if denied:
        return denied
    db = _ctx(request).db
    payload = await _read_json(request)
    folder_id = _safe_int(payload.get("id"))
    name = str(payload.get("name") or "").strip()
    if not name:
        return _error("Укажите название папки")
    if db.scenario_folders.get(folder_id) is None:
        return _error("Папка не найдена", status=404)
    existing = db.scenario_folders.by_name(name)
    if existing and existing.id != folder_id:
        return _error(f"Папка «{name}» уже существует")
    folder = db.scenario_folders.update(folder_id, name=name, updated_at=utcnow_iso())
    return _ok(folder)


async def api_scenario_folders_delete(request: web.Request) -> web.Response:
    """Удаляет папку. Сценарии внутри не удаляются — переезжают в корень."""
    denied = _folders_admin_guard(request)
    if denied:
        return denied
    db = _ctx(request).db
    payload = await _read_json(request)
    folder_id = _safe_int(payload.get("id"))
    if db.scenario_folders.get(folder_id) is None:
        return _error("Папка не найдена", status=404)
    db.scenarios.clear_folder(folder_id)
    db.scenario_folders.delete(folder_id)
    return _ok({"deleted": folder_id})


async def api_scenarios_move(request: web.Request) -> web.Response:
    """Перекладывает сценарии в папку. folder_id=null — вынести в корень."""
    denied = _folders_admin_guard(request)
    if denied:
        return denied
    db = _ctx(request).db
    payload = await _read_json(request)

    raw_ids = payload.get("scenario_ids")
    if not isinstance(raw_ids, list):
        raw_ids = [payload.get("scenario_id")]
    scenario_ids = [_safe_int(x) for x in raw_ids if _safe_int(x)]
    if not scenario_ids:
        return _error("Не указаны сценарии для перемещения")

    raw_folder = payload.get("folder_id")
    folder_id = _safe_int(raw_folder) or None
    if folder_id is not None and db.scenario_folders.get(folder_id) is None:
        return _error("Папка не найдена", status=404)

    now = utcnow_iso()
    moved = []
    for scenario_id in scenario_ids:
        if db.scenarios.get(scenario_id) is None:
            continue
        db.scenarios.update(scenario_id, folder_id=folder_id, updated_at=now)
        moved.append(scenario_id)
    return _ok({"moved": moved, "folder_id": folder_id})