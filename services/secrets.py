"""Шифрование секретов хостов (паролей) для хранения в БД.

Пароли хостов нужны для повторной привязки SSH-ключа (ssh-copy-id), поэтому их
нельзя хранить в виде необратимого хэша — требуется обратимое шифрование.

Схема: для каждого пароля генерируется случайная соль. Из мастер-ключа и соли
через PBKDF2-HMAC-SHA256 выводится ключ Fernet, которым шифруется пароль.
В БД сохраняется строка ``base64(соль):fernet_token`` — соль у каждой записи своя,
поэтому одинаковые пароли дают разные шифртексты.

Мастер-ключ берётся из переменной окружения ``NETRUNNER_SECRET_KEY``; если она не
задана, ключ генерируется один раз и сохраняется в файл ``data/.secret_key``
(права 0600), чтобы расшифровка работала между перезапусками.
"""

from __future__ import annotations

import base64
import os
from pathlib import Path

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

_SALT_BYTES = 16
_KDF_ITERATIONS = 200_000
_SECRET_KEY_FILE = Path("data/.secret_key")

_master_secret: bytes | None = None


def _load_master_secret() -> bytes:
    """Возвращает мастер-ключ из окружения или из persistent-файла."""
    global _master_secret
    if _master_secret is not None:
        return _master_secret

    env_value = os.environ.get("NETRUNNER_SECRET_KEY")
    if env_value:
        _master_secret = env_value.encode("utf-8")
        return _master_secret

    key_file = _SECRET_KEY_FILE
    try:
        if key_file.exists():
            _master_secret = key_file.read_bytes()
            return _master_secret
        key_file.parent.mkdir(parents=True, exist_ok=True)
        generated = base64.urlsafe_b64encode(os.urandom(32))
        # Записываем атомарно с правами 0600, чтобы ключ не утёк.
        fd = os.open(str(key_file), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, generated)
        finally:
            os.close(fd)
        _master_secret = generated
        return _master_secret
    except OSError as exc:
        raise RuntimeError(
            "Не удалось получить мастер-ключ для шифрования: задайте "
            "NETRUNNER_SECRET_KEY или обеспечьте доступ к data/.secret_key"
        ) from exc


def _fernet_for_salt(salt: bytes) -> Fernet:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=_KDF_ITERATIONS,
    )
    derived = kdf.derive(_load_master_secret())
    return Fernet(base64.urlsafe_b64encode(derived))


def encrypt_secret(plaintext: str) -> str:
    """Шифрует пароль и возвращает строку ``base64(соль):fernet_token``."""
    salt = os.urandom(_SALT_BYTES)
    token = _fernet_for_salt(salt).encrypt(plaintext.encode("utf-8"))
    return f"{base64.b64encode(salt).decode('ascii')}:{token.decode('ascii')}"


def decrypt_secret(stored: str) -> str:
    """Расшифровывает строку, полученную из :func:`encrypt_secret`."""
    if not stored or ":" not in stored:
        raise ValueError("Некорректный формат зашифрованного секрета")
    salt_b64, token = stored.split(":", 1)
    salt = base64.b64decode(salt_b64)
    return _fernet_for_salt(salt).decrypt(token.encode("utf-8")).decode("utf-8")
