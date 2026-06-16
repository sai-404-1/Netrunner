from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from typing import TYPE_CHECKING

from database.repos.base import utcnow_iso

if TYPE_CHECKING:
    from database import Database


# In production use a proper key derivation (e.g. bcrypt/argon2). PBKDF2-SHA256 is
# acceptable for a self-contained demo where adding heavy dependencies is undesirable.
_SALT_LEN = 32
_ITERATIONS = 100_000


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

    def register(self, username: str, password: str, email: str | None = None) -> dict:
        if not username or not password:
            return {"ok": False, "error": "username and password are required"}
        if self.db.users.by_username(username):
            return {"ok": False, "error": "username already exists"}

        user = self.db.users.create(
            username=username,
            email=email,
            password_hash=_hash_password(password),
            is_active=1,
            is_superuser=0,
            created_at=utcnow_iso(),
            updated_at=utcnow_iso(),
        )
        return {"ok": True, "user_id": user.id}

    def login(self, username: str, password: str) -> dict:
        user = self.db.users.by_username(username)
        if not user or not user.is_active:
            return {"ok": False, "error": "invalid username or password"}
        if not _verify_password(password, user.password_hash):
            return {"ok": False, "error": "invalid username or password"}
        token = create_access_token()
        self.db.users.update(user.id, token=token)
        return {
            "ok": True,
            "token": token,
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "is_superuser": user.is_superuser,
            },
        }

    def logout(self, user_id: int) -> dict:
        self.db.users.update(user_id, token=None)
        return {"ok": True}

    def me(self, token: str) -> dict | None:
        if not token:
            return None
        user = self.db.users.get_one_by(token=token)
        if not user or not user.is_active:
            return None
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_superuser": user.is_superuser,
        }

    def create_default_user(self, username: str = "admin", password: str = "admin") -> bool:
        """Create a default user if no users exist."""
        if self.db.users.all():
            return False
        self.register(username, password)
        return True
