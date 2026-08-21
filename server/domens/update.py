import asyncio
import os
import subprocess

from aiohttp import web

from database import open_database
from database.repos import utcnow_iso
from server.tools import _require_admin, _error, _ok, _ctx, _read_json
from services.host_service import _run_background
from services.update_service import UpdateService

from services.logger import Logger

logger = Logger()

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


async def api_update_check(request: web.Request) -> web.Response:
    """Проверить наличие обновлений через git."""
    runner_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        result = subprocess.run(
            ["git", "fetch"],
            cwd=runner_dir, capture_output=True, text=True, timeout=30
        )
        result2 = subprocess.run(
            ["git", "rev-list", "--count", "HEAD..@{u}"],
            cwd=runner_dir, capture_output=True, text=True, timeout=15
        )
        behind = result2.stdout.strip()
        if behind and behind.isdigit() and int(behind) > 0:
            log = subprocess.run(
                ["git", "--no-pager", "log", "-1", "@{u}", "--pretty=%B"],
                cwd=runner_dir, capture_output=True, text=True, timeout=15
            )
            diff = subprocess.run(
                ["git", "diff", "--stat", "HEAD..@{u}"],
                cwd=runner_dir, capture_output=True, text=True, timeout=15
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
    runner_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        subprocess.run(["git", "fetch"], cwd=runner_dir, capture_output=True, text=True, timeout=30)
        result = subprocess.run(
            ["git", "diff", "HEAD..@{u}", "--stat"],
            cwd=runner_dir, capture_output=True, text=True, timeout=15
        )
        result2 = subprocess.run(
            ["git", "diff", "HEAD..@{u}", "-p", "--", "*.py", "*.ts", "*.tsx", "*.json", "*.sh", "Dockerfile", "*.yml"],
            cwd=runner_dir, capture_output=True, text=True, timeout=15
        )
        changed_files = subprocess.run(
            ["git", "diff", "--name-only", "HEAD..@{u}"],
            cwd=runner_dir, capture_output=True, text=True, timeout=15
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
    runner_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        result = subprocess.run(
            ["git", "pull"],
            cwd=runner_dir, capture_output=True, text=True, timeout=60
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

# TODO пересмотреть надобность
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
        interval = 1800
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