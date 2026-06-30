#!/usr/bin/env python3
"""NetRunner supervisor (PID 1 контейнера).

Запускает бэкенд и фронтенд как дочерние процессы и обеспечивает:
  • health-check после старта (бэкенд ответил на /healthz);
  • различение намеренного рестарта «на обновление» (маркер data/.updating)
    и неожиданного краша (счётчик падений);
  • «феникс»-recovery: при крэш-лупе сверх порога — откат кода к last_good_commit
    и восстановление БД из снимка, сделанного перед обновлением, затем перезапуск;
  • логирование причины остановки (код выхода + хвост вывода + commit) в
    персистентный лог на томе (data/supervisor.log, data/incidents/).

Спроектировано для деплоя с bind-mount (код на ФС хоста ВМ примонтирован в
контейнер) — только тогда доступны git-операции и пересборка фронта. В текущем
«запечённом образе» (.git нет) git-функции корректно пропускаются: супервизор
просто следит за процессами и перезапускает их. См. CLAUDE.md → «code self-update».

Phase 1: фундамент (супервизия + recovery). Монитор git и применение обновлений —
отдельные фазы; этот модуль предоставляет точки подключения (маркер + снимок БД).
"""

from __future__ import annotations

import collections
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# --- Конфигурация (env с безопасными дефолтами) ---------------------------
APP_DIR = Path(os.environ.get("NETRUNNER_APP_DIR", Path(__file__).resolve().parent))
DATA_DIR = Path(os.environ.get("NETRUNNER_DATA_DIR", APP_DIR / "data"))
FRONTEND_DIR = APP_DIR / "frontend"

PY_HOST = os.environ.get("NETRUNNER_PY_HOST", "127.0.0.1")
PY_PORT = int(os.environ.get("NETRUNNER_PY_PORT", "8000"))
FRONTEND_PORT = int(os.environ.get("NETRUNNER_FRONTEND_PORT", "3000"))

CRASH_THRESHOLD = int(os.environ.get("NETRUNNER_CRASH_THRESHOLD", "3"))
HEALTH_TIMEOUT = int(os.environ.get("NETRUNNER_HEALTH_TIMEOUT", "60"))
HEALTH_URL = f"http://{PY_HOST}:{PY_PORT}/healthz"

STATE_FILE = DATA_DIR / "supervisor_state.json"
LOG_FILE = DATA_DIR / "supervisor.log"
INCIDENTS_DIR = DATA_DIR / "incidents"
UPDATING_MARKER = DATA_DIR / ".updating"          # присутствие = намеренный рестарт на обновление
DB_PATH = DATA_DIR / "netrunner.db"
DB_PRE_UPDATE = DATA_DIR / "netrunner.db.pre_update"  # снимок БД, сделанный перед апдейтом

_TAIL_LINES = 200


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def log(msg: str, level: str = "INFO") -> None:
    line = f"{_now()} [{level}] supervisor: {msg}"
    print(line, flush=True)  # видно в docker logs
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


# --- Состояние -------------------------------------------------------------
def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"last_good_commit": None, "fail_count": 0}


def save_state(state: dict) -> None:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        log(f"не удалось сохранить состояние: {exc}", "WARN")


# --- Git (graceful: no-op если .git отсутствует) ---------------------------
def is_git_repo() -> bool:
    return (APP_DIR / ".git").exists()


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(APP_DIR), *args],
        capture_output=True,
        text=True,
        timeout=120,
    )


def current_commit() -> str | None:
    if not is_git_repo():
        return None
    try:
        r = git("rev-parse", "HEAD")
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:  # noqa: BLE001
        return None


# --- Дочерние процессы с кольцевым буфером вывода --------------------------
class Child:
    def __init__(self, name: str, cmd: list[str], cwd: Path, env: dict):
        self.name = name
        self.cmd = cmd
        self.cwd = cwd
        self.env = env
        self.tail: collections.deque[str] = collections.deque(maxlen=_TAIL_LINES)
        self.proc: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        log(f"запуск {self.name}: {' '.join(self.cmd)}")
        self.proc = subprocess.Popen(
            self.cmd,
            cwd=str(self.cwd),
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()

    def _reader(self) -> None:
        assert self.proc and self.proc.stdout
        for line in self.proc.stdout:
            self.tail.append(line.rstrip("\n"))
            print(f"[{self.name}] {line}", end="", flush=True)

    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def returncode(self) -> int | None:
        return self.proc.poll() if self.proc else None

    def stop(self, timeout: int = 10) -> None:
        if not self.proc or self.proc.poll() is not None:
            return
        self.proc.terminate()
        try:
            self.proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()

    def tail_text(self) -> str:
        return "\n".join(self.tail)


# --- Health-check ----------------------------------------------------------
def wait_health(children: list[Child]) -> bool:
    """Ждёт, пока бэкенд ответит на /healthz. False, если процесс умер или таймаут."""
    deadline = time.time() + HEALTH_TIMEOUT
    while time.time() < deadline:
        if any(not c.alive() for c in children):
            return False  # кто-то умер до готовности
        try:
            with urllib.request.urlopen(HEALTH_URL, timeout=3) as resp:
                if resp.status == 200:
                    return True
        except Exception:  # noqa: BLE001 — ещё не поднялся
            pass
        time.sleep(1)
    return False


# --- Recovery (феникс) -----------------------------------------------------
def rebuild_frontend() -> None:
    """Пересобирает фронтенд (нужно после отката кода). Best-effort при наличии исходников."""
    if not (FRONTEND_DIR / "package.json").exists():
        log("пересборка фронта пропущена: нет исходников (запечённый образ)", "WARN")
        return
    try:
        log("пересборка фронта: npm install && npm run build…")
        subprocess.run(["npm", "install"], cwd=str(FRONTEND_DIR), check=True, timeout=900)
        subprocess.run(["npm", "run", "build"], cwd=str(FRONTEND_DIR), check=True, timeout=900)
        log("фронт пересобран")
    except Exception as exc:  # noqa: BLE001
        log(f"пересборка фронта не удалась: {exc}", "ERROR")


def write_incident(kind: str, detail: str) -> None:
    try:
        INCIDENTS_DIR.mkdir(parents=True, exist_ok=True)
        path = INCIDENTS_DIR / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{kind}.log"
        path.write_text(f"{_now()} [{kind}]\n{detail}\n", encoding="utf-8")
    except OSError:
        pass


def recover(state: dict) -> None:
    """Откат кода к last_good_commit + восстановление БД из снимка перед апдейтом."""
    log("RECOVERY: порог падений достигнут — выполняю откат", "ERROR")
    good = state.get("last_good_commit")
    actions = []

    if is_git_repo() and good:
        try:
            r = git("reset", "--hard", good)
            if r.returncode == 0:
                actions.append(f"код откатан к {good}")
                rebuild_frontend()
            else:
                actions.append(f"git reset не удался: {r.stderr.strip()}")
        except Exception as exc:  # noqa: BLE001
            actions.append(f"ошибка отката кода: {exc}")
    else:
        actions.append("откат кода пропущен (нет git/last_good_commit)")

    if DB_PRE_UPDATE.exists():
        try:
            shutil.copy2(DB_PRE_UPDATE, DB_PATH)
            actions.append("БД восстановлена из снимка перед обновлением")
        except OSError as exc:
            actions.append(f"восстановление БД не удалось: {exc}")
    else:
        actions.append("снимок БД перед обновлением отсутствует — восстановление пропущено")

    state["fail_count"] = 0
    save_state(state)
    detail = "\n".join(actions)
    log("RECOVERY завершён:\n" + detail, "ERROR")
    write_incident("recovery", detail)


# --- Главный цикл ----------------------------------------------------------
_stop_requested = False


def _on_signal(signum, _frame):
    global _stop_requested
    _stop_requested = True
    log(f"получен сигнал {signum}, останавливаюсь")


def build_children() -> list[Child]:
    env = {**os.environ, "HOME": os.environ.get("HOME", "/root")}
    children = [
        Child(
            "backend",
            [sys.executable, "-m", "web_main", "--host", PY_HOST, "--port", str(PY_PORT)],
            APP_DIR,
            env,
        )
    ]
    if (FRONTEND_DIR / "server.js").exists():
        children.append(
            Child("frontend", ["node", "server.js"], FRONTEND_DIR, {**env, "PORT": str(FRONTEND_PORT)})
        )
    else:
        log("frontend/server.js не найден — запускаю только бэкенд", "WARN")
    return children


def run() -> int:
    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    log(f"старт. APP_DIR={APP_DIR} git={'да' if is_git_repo() else 'нет'} "
        f"порог падений={CRASH_THRESHOLD}")

    state = load_state()
    pending_rebuild = False

    while not _stop_requested:
        # Применённое обновление меняет код на диске (git reset делает бэкенд перед
        # выходом) — перед стартом нужно пересобрать фронт.
        if pending_rebuild:
            rebuild_frontend()
            pending_rebuild = False

        commit = current_commit()
        children = build_children()
        for c in children:
            c.start()

        healthy = wait_health(children)
        if healthy:
            log("health-check пройден: проект поднялся корректно")
            if commit:
                state["last_good_commit"] = commit
            state["fail_count"] = 0
            save_state(state)
        else:
            log("health-check НЕ пройден", "WARN")

        # Ждём, пока какой-либо дочерний процесс завершится (или придёт сигнал).
        while not _stop_requested and all(c.alive() for c in children):
            time.sleep(1)

        if _stop_requested:
            for c in children:
                c.stop()
            break

        # Какой-то процесс упал — гасим остальные.
        codes = {c.name: c.returncode() for c in children}
        for c in children:
            c.stop()

        # Маркер проверяем ИМЕННО здесь: приложение пишет его прямо перед выходом
        # при применении обновления.
        if UPDATING_MARKER.exists():
            try:
                UPDATING_MARKER.unlink()
            except OSError:
                pass
            pending_rebuild = True
            log("намеренный рестарт на обновление — пересоберу фронт и перезапущу (не падение)")
            continue

        # Неожиданное завершение = краш.
        state["fail_count"] = int(state.get("fail_count", 0)) + 1
        save_state(state)
        tails = "\n\n".join(f"--- {c.name} (exit={codes.get(c.name)}) ---\n{c.tail_text()}" for c in children)
        detail = f"коды выхода: {codes}\ncommit: {commit}\nсчётчик падений: {state['fail_count']}/{CRASH_THRESHOLD}\n\n{tails}"
        log(f"проект завершился неожиданно (падение {state['fail_count']}/{CRASH_THRESHOLD}), коды: {codes}", "WARN")
        write_incident("crash", detail)

        if state["fail_count"] >= CRASH_THRESHOLD:
            recover(state)
        else:
            time.sleep(2)  # короткая пауза перед перезапуском

    log("супервизор остановлен")
    return 0


if __name__ == "__main__":
    sys.exit(run())
