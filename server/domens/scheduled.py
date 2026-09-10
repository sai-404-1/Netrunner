from aiohttp import web
import json
from datetime import datetime, timezone
from types import SimpleNamespace

from server.tools import _ok, _ctx, _read_json, _safe_int
from database.repos.schedule_repo import validate_schedule, next_slot_utc_iso


def _to_utc_iso(value) -> str:
    """Нормализует строку времени в UTC ISO (для run_at).

    Фронт шлёт run_at в ЛОКАЛЬНОМ времени со смещением (напр. +03:00), а
    планировщик (due/mark_ran/recurring-слоты) оперирует в UTC (+00:00) и
    сравнивает ISO-строки. Лексикографическое сравнение дат с РАЗНЫМИ офсетами
    некорректно (03:08+03:00 «больше» 00:22+00:00, хотя это один момент) — поэтому
    всё время приводим к UTC здесь, на входе. Пусто/битое -> ''.
    """
    raw = str(value or "").strip()
    if not raw:
        return ""
    txt = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        dt = datetime.fromisoformat(txt)
    except ValueError:
        return ""
    if dt.tzinfo is None:
        # Наивное время — считаем его локальным временем сервера.
        dt = dt.astimezone()
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _days(payload) -> str:
    """days_of_week из payload, обрезанный; '' если расписание не задано."""
    return str(payload.get("days_of_week") or "").strip()


def _int_opt(payload, key):
    """Число из payload или None (0 — валидное значение!)."""
    v = payload.get(key)
    return int(v) if v is not None else None


def _id_list(payload, key) -> list[int]:
    """Массив id из payload (target_host_ids, scenario_ids, ...) или []."""
    raw = payload.get(key)
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        return [int(x) for x in raw if x is not None]
    # Строка вида "1,2,3" — на случай форм, шлющих строкой.
    return [int(x) for x in str(raw).split(",") if x.strip()]


def _multi_params(payload) -> dict:
    """Разбирает мульти-выбор из payload (JSON-колонки). Возвращает {} если не задан."""
    host_ids = _id_list(payload, "target_host_ids")
    group_ids = _id_list(payload, "target_group_ids")
    scenario_ids = _id_list(payload, "scenario_ids")
    result = {}
    if host_ids:
        result["target_host_ids_json"] = json.dumps(host_ids)
    if group_ids:
        result["target_group_ids_json"] = json.dumps(group_ids)
    if scenario_ids:
        result["scenario_ids_json"] = json.dumps(scenario_ids)
    return result


def _schedule_params(payload) -> dict:
    """Разбирает recurring-поля и валидирует. Бросает web.HTTPBadRequest при ошибке."""
    days = _days(payload)
    start_min = _int_opt(payload, "start_min")
    end_min = _int_opt(payload, "end_min")
    interval_min = _int_opt(payload, "interval_min")
    if not any(ch == "1" for ch in days):
        return {}
    try:
        validate_schedule(days, start_min, end_min, interval_min)
    except ValueError as exc:
        raise web.HTTPBadRequest(reason=str(exc))
    return {
        "days_of_week": days,
        "start_min": start_min,
        "end_min": end_min,
        "interval_min": interval_min,
    }


def _first_run_at_utc(sched: dict) -> str:
    """Первый будущий слот расписания как UTC ISO для run_at (создание задачи)."""
    fake = SimpleNamespace(**sched)
    run_at = next_slot_utc_iso(datetime.now().astimezone(), fake)
    if not run_at:
        raise web.HTTPBadRequest(reason="Не удалось вычислить первый слот расписания")
    return run_at


async def api_scheduled(request: web.Request) -> web.Response:
    return _ok(_ctx(request).db.scheduled.all())


async def api_active_scheduled(request: web.Request) -> web.Response:
    return _ok(_ctx(request).db.scheduled.filter(is_enabled=True))


async def api_inactive_scheduled(request: web.Request) -> web.Response:
    return _ok(_ctx(request).db.scheduled.filter(is_enabled=False))


async def api_schedule_create(request: web.Request) -> web.Response:
    ctx = _ctx(request)
    payload = await _read_json(request)
    scenario_ids = _id_list(payload, "scenario_ids")
    legacy_scenario_id = _safe_int(payload.get("scenario_id"))
    # Сбор: явный список сценариев (мульти) либо одиночный scenario_id (legacy).
    if legacy_scenario_id and not scenario_ids:
        scenario_ids = [legacy_scenario_id]
    if not scenario_ids:
        raise web.HTTPBadRequest(reason="Не указан сценарий (scenario_ids)")

    sched = _schedule_params(payload)
    if sched:
        # Recurring-расписание: run_at = первый будущий слот (расписание не стартует
        # «в прошлом» и не срабатывает мгновенно при создании); wait/простой интервал
        # с расписанием несовместимы — сбрасываем.
        run_at = _first_run_at_utc(sched)
        wait_for_online = 0
        interval_seconds = None
    else:
        run_at = _to_utc_iso(payload.get("run_at"))
        if not run_at:
            raise web.HTTPBadRequest(reason="run_at is required (или задайте расписание)")
        wait_for_online = payload.get("wait_for_online")
        interval_seconds = payload.get("interval_seconds")
        sched = {
            "days_of_week": "",
            "start_min": None,
            "end_min": None,
            "interval_min": None,
        }

    multi = _multi_params(payload)
    max_runs_raw = payload.get("max_runs")
    scheduled = ctx.db.scheduled.create(
        name=str(payload.get("name") or "").strip(),
        description=str(payload.get("description") or "").strip() or None,
        scenario_id=scenario_ids[0],
        target_type=str(payload.get("target_type") or "host").strip(),
        target_id=_safe_int(payload.get("target_id")) or 0,
        run_at=run_at,
        is_enabled=1 if payload.get("is_enabled", True) else 0,
        wait_for_online=1 if wait_for_online else 0,

        # TODO проверить что из-за None нет последствий и найти причину по которой возможен None
        interval_seconds=int(interval_seconds) if interval_seconds else None,
        max_runs=int(max_runs_raw) if max_runs_raw else None,
        **sched,
        **multi,
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
        if updates["scenario_id"] is None:
            updates.pop("scenario_id")
    if "target_id" in updates:
        updates["target_id"] = _safe_int(updates["target_id"])
    if "run_at" in updates and updates["run_at"]:
        updates["run_at"] = _to_utc_iso(updates["run_at"])

    # Мульти-выбор сценариев: явный список scenario_ids перезаписывает.
    scenario_ids = _id_list(payload, "scenario_ids")
    multi = _multi_params(payload)
    if multi:
        updates["scenario_id"] = scenario_ids[0] if scenario_ids else None
        updates.update(multi)

    # Если передан recurring-набор — валидируем и пересчитываем run_at (следующий
    # слот), сбрасываем несовместимые wait_for_online и простой интервал.
    if any(ch == "1" for ch in _days(payload)):
        sched = _schedule_params(payload)
        if sched:
            updates["run_at"] = _first_run_at_utc(sched)
            updates["wait_for_online"] = 0
            updates["interval_seconds"] = None
            updates.update(sched)

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