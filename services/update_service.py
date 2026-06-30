"""Сервис самообновления кода через git (Phase 2 — монитор + применение).

Хранит конфиг (git-remote, ветка, deploy-токен в шифре, интервал, авто-флаг) в
таблице app_settings. Умеет:
  • check() — git fetch + сравнение локального HEAD с origin/<branch> (read-only);
  • apply() — снимок БД (pre_update) + git reset на origin/<branch> + маркер .updating,
    после чего процесс завершается, а супервизор пересобирает фронт и стартует новый код
    (см. supervise.py). Откат при крэш-лупе делает супервизор.

git-функции — graceful no-op без git-чекаута (в запечённом образе). Применение
живёт только при bind-mount-деплое (Phase 4).
"""

from __future__ import annotations

import base64
import os
import shutil
import sqlite3
import subprocess
from pathlib import Path

from services.secrets import decrypt_secret, encrypt_secret

APP_DIR = Path(os.environ.get("NETRUNNER_APP_DIR", Path(__file__).resolve().parent.parent))
DATA_DIR = Path(os.environ.get("NETRUNNER_DATA_DIR", APP_DIR / "data"))
UPDATING_MARKER = DATA_DIR / ".updating"
DB_PATH = DATA_DIR / "netrunner.db"
DB_PRE_UPDATE = DATA_DIR / "netrunner.db.pre_update"

# Ключи в app_settings.
_K_REMOTE = "git_remote"
_K_BRANCH = "git_branch"
_K_TOKEN = "git_token_enc"
_K_AUTO = "auto_update"
_K_INTERVAL = "poll_interval"


class UpdateService:
    def __init__(self, db):
        self.db = db

    # --- конфиг ------------------------------------------------------------
    def get_config(self) -> dict:
        s = self.db.app_settings
        token_enc = s.get(_K_TOKEN)
        return {
            "remote": s.get(_K_REMOTE, ""),
            "branch": s.get(_K_BRANCH, ""),
            "has_token": bool(token_enc),
            "auto_update": s.get(_K_AUTO, "0") == "1",
            "poll_interval": int(s.get(_K_INTERVAL, "600") or "600"),
        }

    def set_config(
        self,
        remote: str | None = None,
        branch: str | None = None,
        token: str | None = None,
        auto_update: bool | None = None,
        poll_interval: int | None = None,
    ) -> dict:
        s = self.db.app_settings
        if remote is not None:
            s.set(_K_REMOTE, remote.strip())
            # Привязываем origin к указанному URL (без токена — авторизация через заголовок).
            if remote.strip() and self.is_git_repo():
                r = self._git("remote", "set-url", "origin", remote.strip())
                if r.returncode != 0:  # origin ещё не существует
                    self._git("remote", "add", "origin", remote.strip())
        if branch is not None:
            s.set(_K_BRANCH, branch.strip())
        if token is not None:
            # Пустая строка = очистить токен.
            s.set(_K_TOKEN, encrypt_secret(token) if token else None)
        if auto_update is not None:
            s.set(_K_AUTO, "1" if auto_update else "0")
        if poll_interval is not None:
            s.set(_K_INTERVAL, str(max(60, int(poll_interval))))
        return self.get_config()

    def _token(self) -> str | None:
        enc = self.db.app_settings.get(_K_TOKEN)
        if not enc:
            return None
        try:
            return decrypt_secret(enc)
        except Exception:  # noqa: BLE001
            return None

    # --- git ---------------------------------------------------------------
    def is_git_repo(self) -> bool:
        return (APP_DIR / ".git").exists()

    def _auth_args(self) -> list[str]:
        token = self._token()
        if not token:
            return []
        # Basic-заголовок с PAT — совместимо с GitHub/GitLab по HTTPS.
        cred = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        return ["-c", f"http.extraHeader=Authorization: Basic {cred}"]

    def _git(self, *args: str, auth: bool = False, timeout: int = 120) -> subprocess.CompletedProcess:
        cmd = ["git", "-C", str(APP_DIR)]
        if auth:
            cmd += self._auth_args()
        cmd += list(args)
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        return subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=timeout)

    def _branch(self) -> str:
        cfg = self.db.app_settings.get(_K_BRANCH)
        if cfg:
            return cfg
        r = self._git("rev-parse", "--abbrev-ref", "HEAD")
        return r.stdout.strip() or "main"

    def check(self) -> dict:
        """git fetch + сравнение HEAD с origin/<branch>. read-only."""
        if not self.is_git_repo():
            return {"git": False, "error": "Каталог не является git-репозиторием (нужен bind-mount деплой)"}
        branch = self._branch()
        fetch = self._git("fetch", "origin", branch, auth=True)
        if fetch.returncode != 0:
            return {"git": True, "branch": branch, "error": f"git fetch не удался: {fetch.stderr.strip()[:300]}"}
        local = self._git("rev-parse", "HEAD").stdout.strip()
        remote = self._git("rev-parse", f"origin/{branch}").stdout.strip()
        behind_r = self._git("rev-list", "--count", f"HEAD..origin/{branch}")
        behind = int(behind_r.stdout.strip() or "0") if behind_r.returncode == 0 else 0
        last = self._git("log", "-1", "--format=%h %s", f"origin/{branch}").stdout.strip()
        stats = self._git("diff", "--stat", f"HEAD..origin/{branch}").stdout.strip() if behind else ""
        return {
            "git": True,
            "branch": branch,
            "local": local,
            "remote": remote,
            "behind": behind,
            "up_to_date": behind == 0,
            "last_remote": last,
            "diff_stats": stats,
        }

    # --- применение --------------------------------------------------------
    def _snapshot_db(self) -> bool:
        """Согласованный снимок БД через SQLite Online Backup (как в админке)."""
        if not DB_PATH.exists():
            return False
        try:
            src = sqlite3.connect(str(DB_PATH))
            dst = sqlite3.connect(str(DB_PRE_UPDATE))
            with dst:
                src.backup(dst)
            dst.close()
            src.close()
            return True
        except sqlite3.Error:
            return False

    def apply(self) -> dict:
        """Снимок БД → git reset на origin/<branch> → маркер. Возврат результата.

        Реальный перезапуск/пересборку делает супервизор после выхода процесса —
        вызывающий код (эндпоинт) обязан завершить процесс после ответа.
        """
        if not self.is_git_repo():
            return {"ok": False, "error": "Нет git-репозитория (нужен bind-mount деплой)"}
        status = self.check()
        if status.get("error"):
            return {"ok": False, "error": status["error"]}
        if status.get("up_to_date"):
            return {"ok": False, "error": "Уже актуальная версия"}

        branch = status["branch"]
        snap = self._snapshot_db()
        reset = self._git("reset", "--hard", f"origin/{branch}", auth=False)
        if reset.returncode != 0:
            return {"ok": False, "error": f"git reset не удался: {reset.stderr.strip()[:300]}"}

        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            UPDATING_MARKER.write_text(status.get("remote", ""), encoding="utf-8")
        except OSError as exc:
            return {"ok": False, "error": f"не удалось записать маркер обновления: {exc}"}

        return {
            "ok": True,
            "applied_to": status.get("remote"),
            "db_snapshot": snap,
            "message": "Код обновлён. Перезапуск и пересборка фронта выполнит супервизор.",
        }
