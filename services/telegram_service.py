"""Интеграция с Telegram: привязка/верификация аккаунта в личном кабинете.

Поток: пользователь в кабинете жмёт «Привязать Telegram» → бэкенд генерирует одноразовый
код и ссылку t.me/<bot>?start=<code> → пользователь открывает бота и жмёт Start →
фоновый поллер (getUpdates) ловит `/start <code>`, сверяет код и привязывает chat_id к
пользователю. Это фундамент для 2FA при входе (подтверждение через Telegram).

Токен бота хранится в app_settings (зашифрован через secrets.py) либо в env
NETRUNNER_TELEGRAM_BOT_TOKEN. Бот для NetRunner должен быть ОТДЕЛЬНЫМ (не общий с другими
сервисами), иначе getUpdates конфликтует.
"""

from __future__ import annotations

import json
import secrets as _secrets
import urllib.error
import urllib.request
import os
from datetime import datetime, timedelta, timezone

from services.secrets import decrypt_secret, encrypt_secret

_K_TOKEN = "telegram_bot_token"
_K_BOT_USERNAME = "telegram_bot_username"
_K_OFFSET = "telegram_update_offset"
_LINK_TTL_MIN = 10


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class TelegramService:
    def __init__(self, db):
        self.db = db

    # --- токен/конфиг -------------------------------------------------------
    def _token(self) -> str | None:
        env = os.environ.get("NETRUNNER_TELEGRAM_BOT_TOKEN")
        if env:
            return env.strip()
        enc = self.db.app_settings.get(_K_TOKEN)
        if not enc:
            return None
        try:
            return decrypt_secret(enc)
        except Exception:  # noqa: BLE001
            return None

    def configured(self) -> bool:
        return bool(self._token())

    def set_token(self, token: str | None) -> None:
        self.db.app_settings.set(_K_TOKEN, encrypt_secret(token) if token else None)
        self.db.app_settings.set(_K_BOT_USERNAME, None)  # сбросить кэш имени бота

    # --- низкоуровневый вызов Bot API --------------------------------------
    def _api(self, method: str, params: dict | None = None, timeout: int = 20) -> dict | None:
        token = self._token()
        if not token:
            return None
        url = f"https://api.telegram.org/bot{token}/{method}"
        body = json.dumps(params or {}).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                return json.loads(exc.read().decode("utf-8"))
            except Exception:  # noqa: BLE001
                return None
        except Exception:  # noqa: BLE001 — сеть/таймаут
            return None

    def get_bot_username(self) -> str | None:
        cached = self.db.app_settings.get(_K_BOT_USERNAME)
        if cached:
            return cached
        data = self._api("getMe", {}, timeout=10)
        if data and data.get("ok"):
            uname = (data.get("result") or {}).get("username")
            if uname:
                self.db.app_settings.set(_K_BOT_USERNAME, uname)
            return uname
        return None

    def send_message(self, chat_id, text: str) -> dict | None:
        return self._api("sendMessage", {"chat_id": chat_id, "text": text})

    # --- привязка ----------------------------------------------------------
    def status(self, user) -> dict:
        return {
            "configured": self.configured(),
            "linked": bool(getattr(user, "telegram_chat_id", None)),
            "username": getattr(user, "telegram_username", None),
            "chat_id": getattr(user, "telegram_chat_id", None),
        }

    def create_link_code(self, user) -> dict:
        if not self.configured():
            return {"ok": False, "error": "Telegram-бот не настроен администратором"}
        code = _secrets.token_hex(4)  # 8 hex-символов
        expires = (datetime.now(timezone.utc) + timedelta(minutes=_LINK_TTL_MIN)).replace(microsecond=0).isoformat()
        self.db.users.update(user.id, telegram_link_code=code, telegram_link_expires=expires)
        bot = self.get_bot_username()
        return {
            "ok": True,
            "code": code,
            "bot_username": bot,
            "deep_link": f"https://t.me/{bot}?start={code}" if bot else None,
            "expires": expires,
            "ttl_minutes": _LINK_TTL_MIN,
        }

    def unlink(self, user_id: int) -> None:
        self.db.users.update(
            user_id,
            telegram_chat_id=None,
            telegram_username=None,
            telegram_link_code=None,
            telegram_link_expires=None,
        )

    # --- поллер ------------------------------------------------------------
    def poll_once(self) -> int:
        """Одна итерация getUpdates: ловит `/start <code>` и привязывает аккаунты."""
        if not self.configured():
            return 0
        params: dict = {"timeout": 0, "allowed_updates": ["message"]}
        offset = self.db.app_settings.get(_K_OFFSET)
        if offset:
            params["offset"] = int(offset)
        data = self._api("getUpdates", params, timeout=25)
        if not data or not data.get("ok"):
            return 0
        updates = data.get("result", [])
        last_id = None
        linked = 0
        for upd in updates:
            last_id = upd.get("update_id")
            msg = upd.get("message") or {}
            text = (msg.get("text") or "").strip()
            if text.startswith("/start"):
                parts = text.split(maxsplit=1)
                code = parts[1].strip() if len(parts) > 1 else ""
                if code and self._try_link(code, msg):
                    linked += 1
        if last_id is not None:
            self.db.app_settings.set(_K_OFFSET, str(last_id + 1))
        return linked

    def _try_link(self, code: str, msg: dict) -> bool:
        user = self.db.users.get_one_by(telegram_link_code=code)
        if not user:
            return False
        exp = getattr(user, "telegram_link_expires", None)
        if exp and exp < _now_iso():
            return False  # код истёк
        chat = msg.get("chat") or {}
        frm = msg.get("from") or {}
        self.db.users.update(
            user.id,
            telegram_chat_id=str(chat.get("id")),
            telegram_username=frm.get("username"),
            telegram_link_code=None,
            telegram_link_expires=None,
        )
        self.send_message(chat.get("id"), f"✅ Telegram привязан к аккаунту «{user.username}» в NetRunner.")
        return True
