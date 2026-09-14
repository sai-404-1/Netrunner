"""Профиль хоста: страница отдельной машины — данные, живые метрики, действия.

Действия фильтруются по уровню доступа пользователя (см. `_host_permissions`):
роль решает, что человек может делать с конкретным компьютером. Это базовый
слой под будущую полноценную модель ролей — сейчас права выводятся из
`is_superuser` / `role` и из уже существующих таблиц доступа
(`user_group_access`, `user_module_access`), новых таблиц не заводит.
"""

from __future__ import annotations

import json

from aiohttp import web

from server.tools import _ctx, _ok, _error, _read_json, _safe_int, model_to_dict, allowed_host_ids

# Живая сводка по машине одним SSH-заходом: два среза /proc/stat с паузой дают
# загрузку CPU, остальное читается один раз. Каждая строка — KEY:value, чтобы
# отсутствие любого источника (нет nvidia-smi, нет /proc/meminfo) просто убирало
# строку, а не ломало разбор.
_METRICS_COMMAND = r"""
awk '/^cpu /{print "CPU1:"$2+$3+$4+$5+$6+$7+$8" "$5+$6}' /proc/stat 2>/dev/null
sleep 0.5
awk '/^cpu /{print "CPU2:"$2+$3+$4+$5+$6+$7+$8" "$5+$6}' /proc/stat 2>/dev/null
awk '/^MemTotal:/{print "MEM_TOTAL:"$2}
     /^MemAvailable:/{print "MEM_AVAIL:"$2}
     /^SwapTotal:/{print "SWAP_TOTAL:"$2}
     /^SwapFree:/{print "SWAP_FREE:"$2}' /proc/meminfo 2>/dev/null
df -P -k / 2>/dev/null | awk 'NR==2{print "DISK_TOTAL:"$2; print "DISK_USED:"$3}'
echo "CORES:$(nproc 2>/dev/null)"
echo "UPTIME:$(cut -d' ' -f1 /proc/uptime 2>/dev/null)"
echo "LOAD:$(cut -d' ' -f1-3 /proc/loadavg 2>/dev/null)"
echo "HOSTNAME:$(hostname 2>/dev/null)"
nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total \
    --format=csv,noheader,nounits 2>/dev/null | head -n1 | sed 's/^/GPU:/'
""".strip()


# --- права ---------------------------------------------------------------

def _host_visible(ctx, user, host_id: int) -> bool:
    """Виден ли хост пользователю. Использует тот же расчёт доступа, что и
    `api_hosts` (см. `allowed_host_ids`): суперпользователь и «обычный»
    пользователь без выданных кабинетов видят всё, преподаватель — только
    хосты из своих кабинетов."""
    host_ids = allowed_host_ids(ctx.db, user)
    if host_ids is None:
        return True
    return host_id in host_ids


def _host_permissions(ctx, user) -> dict:
    """Что роль пользователя позволяет делать с машиной на странице профиля.

    - администратор — всё;
    - преподаватель — всё оперативное (проверка, терминал, питание, запуск
      модулей), но не правку реквизитов машины, ключей и удаление;
    - остальные — только смотреть и проверять доступность.
    """
    is_admin = bool(user and user.get("is_superuser"))
    role = (user or {}).get("role") or "user"
    is_teacher = role == "teacher" and not is_admin

    return {
        "view": True,
        "check": True,
        "terminal": is_admin or is_teacher,
        "power": is_admin or is_teacher,
        "run_modules": is_admin or is_teacher,
        "edit": is_admin or is_teacher,
        "reprovision": is_admin,
        "delete": is_admin,
    }


def _allowed_modules(ctx, user) -> list:
    """Модули, доступные пользователю — запуск в контексте профиля работает
    ровно тем же набором, что и страница модулей."""
    db = ctx.db
    denied_ids: set[int] = set()
    if user and not user.get("is_superuser"):
        for row in db.user_module_access.by_user(user["id"]):
            if not row.allowed:
                denied_ids.add(row.module_id)

    runtime_modules = {item.slug: item for item in ctx.module_registry.all()}
    modules = []
    for row in db.modules.all():
        if row.id in denied_ids:
            continue
        runtime = runtime_modules.get(row.slug)
        if not (runtime and runtime.supports_task_runner):
            continue
        admin_only = bool(getattr(runtime.instance, "admin_only", False))
        if admin_only and not (user and user.get("is_superuser")):
            continue
        modules.append({
            "id": row.id,
            "name": row.name,
            "slug": row.slug,
            "description": row.description,
            "schema_json": row.schema_json,
            "admin_only": admin_only,
        })
    return modules


# --- метрики -------------------------------------------------------------

def _parse_metrics(raw: str) -> dict:
    """Разбирает вывод `_METRICS_COMMAND`. Любое недостающее поле остаётся None —
    страница профиля рисует прочерк, а не падает."""
    values: dict[str, str] = {}
    for line in (raw or "").splitlines():
        key, sep, value = line.partition(":")
        if sep:
            values[key.strip()] = value.strip()

    def _num(key: str) -> float | None:
        try:
            return float(values[key])
        except (KeyError, ValueError):
            return None

    # CPU: доля не-idle тиков между двумя срезами.
    cpu_percent = None
    try:
        total1, idle1 = (float(x) for x in values["CPU1"].split())
        total2, idle2 = (float(x) for x in values["CPU2"].split())
        d_total, d_idle = total2 - total1, idle2 - idle1
        if d_total > 0:
            cpu_percent = round(max(0.0, min(100.0, (d_total - d_idle) / d_total * 100)), 1)
    except (KeyError, ValueError):
        pass

    def _pair_mb(total_key: str, free_key: str) -> dict:
        """Значения /proc/meminfo приходят в килобайтах."""
        total_kb, free_kb = _num(total_key), _num(free_key)
        if total_kb is None or free_kb is None or total_kb <= 0:
            return {"used_mb": None, "total_mb": None, "percent": None}
        used_kb = total_kb - free_kb
        return {
            "used_mb": round(used_kb / 1024),
            "total_mb": round(total_kb / 1024),
            "percent": round(used_kb / total_kb * 100, 1),
        }

    disk = {"used_gb": None, "total_gb": None, "percent": None}
    disk_total_kb, disk_used_kb = _num("DISK_TOTAL"), _num("DISK_USED")
    if disk_total_kb and disk_used_kb is not None and disk_total_kb > 0:
        disk = {
            "used_gb": round(disk_used_kb / 1024 / 1024, 1),
            "total_gb": round(disk_total_kb / 1024 / 1024, 1),
            "percent": round(disk_used_kb / disk_total_kb * 100, 1),
        }

    gpu = None
    if values.get("GPU"):
        parts = [p.strip() for p in values["GPU"].split(",")]
        if len(parts) >= 4:
            def _int(value: str) -> int | None:
                try:
                    return int(float(value))
                except ValueError:
                    return None
            vram_used, vram_total = _int(parts[2]), _int(parts[3])
            gpu = {
                "name": parts[0],
                "percent": _int(parts[1]),
                "vram_used_mb": vram_used,
                "vram_total_mb": vram_total,
                "vram_percent": (
                    round(vram_used / vram_total * 100, 1)
                    if vram_used is not None and vram_total else None
                ),
            }

    cores = _num("CORES")
    return {
        "cpu": {
            "percent": cpu_percent,
            "cores": int(cores) if cores else None,
            "load": values.get("LOAD") or None,
        },
        "ram": _pair_mb("MEM_TOTAL", "MEM_AVAIL"),
        "swap": _pair_mb("SWAP_TOTAL", "SWAP_FREE"),
        "disk": disk,
        "gpu": gpu,
        "uptime_seconds": int(_num("UPTIME") or 0) or None,
        "hostname": values.get("HOSTNAME") or None,
    }


# --- эндпоинты -----------------------------------------------------------

async def api_host_profile(request: web.Request) -> web.Response:
    """Всё, что нужно странице профиля, одним запросом: сама машина, её группа,
    ключ, агент, последняя инвентаризация, таймлайн событий, права и модули."""
    ctx = _ctx(request)
    user = request.get("auth_user")
    host_id = _safe_int(request.match_info["id"])

    host = ctx.db.hosts.get(host_id)
    if host is None:
        return _error("Хост не найден", status=404)
    if not _host_visible(ctx, user, host_id):
        return _error("Нет доступа к этому хосту", status=403)

    item = model_to_dict(host)
    item["last_seen"] = host.last_seen_at
    group = ctx.db.groups.first_group_for_host(host_id)
    item["group_id"] = group.id if group else None
    item["group_name"] = group.name if group else None

    key = ctx.db.ssh_keys.get(host.ssh_key_id) if host.ssh_key_id else None
    item["ssh_key_name"] = key.name if key else None

    agent = ctx.db.host_agents.by_host(host_id)
    item["agent"] = (
        {"status": agent.status, "last_seen_at": agent.last_seen_at, "ssh_username": agent.ssh_username}
        if agent else None
    )

    return _ok({
        "host": item,
        "inventory": model_to_dict(ctx.db.inventory.latest_for_host(host_id)),
        "events": model_to_dict(ctx.db.host_events.for_host(host_id, limit=30)),
        "permissions": _host_permissions(ctx, user),
        "modules": _allowed_modules(ctx, user),
    })


async def api_host_metrics(request: web.Request) -> web.Response:
    """Живая загрузка машины (CPU/RAM/диск/GPU) — снимается по SSH на запрос.

    Хост может быть выключен или недоступен: это не ошибка страницы, поэтому
    возвращаем ok с `available: false` и текстом, а не 500 — профиль продолжает
    показывать остальные данные.
    """
    ctx = _ctx(request)
    user = request.get("auth_user")
    host_id = _safe_int(request.match_info["id"])

    host = ctx.db.hosts.get(host_id)
    if host is None:
        return _error("Хост не найден", status=404)
    if not _host_visible(ctx, user, host_id):
        return _error("Нет доступа к этому хосту", status=403)

    computer = ctx.host_service.to_computer(host)
    try:
        raw = await computer.async_executor_ssh(_METRICS_COMMAND)
    except Exception as exc:  # noqa: BLE001
        return _ok({"available": False, "error": str(exc)})

    if raw.startswith("[ERROR]") or raw.startswith("Error:"):
        return _ok({"available": False, "error": raw})

    return _ok({"available": True, **_parse_metrics(raw)})


async def api_host_power(request: web.Request) -> web.Response:
    """Перезагрузка / выключение машины со страницы профиля.

    Команда уходит в фон на самой машине (`nohup ... &`): иначе SSH обрывается
    вместе с уходящим в перезагрузку хостом и мы получаем ложную ошибку.
    """
    ctx = _ctx(request)
    user = request.get("auth_user")
    payload = await _read_json(request)
    host_id = _safe_int(request.match_info["id"])

    host = ctx.db.hosts.get(host_id)
    if host is None:
        return _error("Хост не найден", status=404)
    if not _host_visible(ctx, user, host_id):
        return _error("Нет доступа к этому хосту", status=403)
    if not _host_permissions(ctx, user)["power"]:
        return _error("Управление питанием недоступно для вашей роли", status=403)

    action = str(payload.get("action") or "").strip()
    commands = {"reboot": "sudo -n systemctl reboot", "poweroff": "sudo -n systemctl poweroff"}
    if action not in commands:
        return _error("Неизвестное действие — ожидается reboot или poweroff", status=400)

    computer = ctx.host_service.to_computer(host)
    command = f"nohup sh -c 'sleep 1; {commands[action]}' >/dev/null 2>&1 & echo scheduled"
    try:
        raw = await computer.async_executor_ssh(command)
    except Exception as exc:  # noqa: BLE001
        return _error(f"Не удалось отправить команду: {exc}", status=502)

    if raw.startswith("[ERROR]") or raw.startswith("Error:"):
        return _error(f"Не удалось отправить команду:\n{raw}", status=502)

    ctx.db.host_events.record(
        host_id,
        f"power_{action}",
        payload_json=json.dumps(
            {"by": (user or {}).get("username"), "action": action}, ensure_ascii=False
        ),
    )
    # Машина уходит в оффлайн — не ждём следующей проверки, чтобы показать это.
    ctx.db.hosts.update(host_id, is_active=0)
    return _ok({"action": action, "host_id": host_id, "output": raw})
