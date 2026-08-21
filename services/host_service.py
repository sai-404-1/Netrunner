from __future__ import annotations

import asyncio
import base64
import hashlib
import os
import re
import subprocess
from pathlib import Path
from typing import Iterable, Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa
from cryptography.hazmat.primitives.serialization import BestAvailableEncryption, NoEncryption

from computer import Computer
from database.repos.base import utcnow_iso
from services.secrets import decrypt_secret, encrypt_secret


class HostService:
    def __init__(self, db):
        self.db = db

    def import_legacy_hosts_json(self, path: str | Path, ssh_key_id: int | None = None) -> int:
        return self.db.import_legacy_hosts_json(path, ssh_key_id=ssh_key_id)

    def all_hosts(self):
        return self.db.hosts.all()

    def active_hosts(self):
        return self.db.hosts.filter(is_active=1)

    def get_host(self, host_id: int):
        return self.db.hosts.get(host_id)

    def add_host(
        self,
        name: str,
        address: str,
        username: str,
        port: int = 22,
        ssh_key_id: int | None = None,
        description: str | None = None,
        password: str | None = None,
    ):
        return self.db.hosts.create(
            name=name,
            address=address,
            username=username,
            port=port,
            ssh_key_id=ssh_key_id,
            description=description,
            password_encrypted=encrypt_secret(password) if password else None,
        )

    def remove_host(self, host_id: int) -> bool:
        return self.db.hosts.delete(host_id)

    def set_host_password(self, host_id: int, password: str):
        """Сохраняет (зашифрованный) пароль хоста для повторной привязки ключа."""
        return self.db.hosts.update(
            host_id, password_encrypted=encrypt_secret(password)
        )

    def get_host_password(self, host_id: int) -> str | None:
        """Возвращает расшифрованный пароль хоста или None, если он не сохранён."""
        host = self.get_host(host_id)
        if not host or not getattr(host, "password_encrypted", None):
            return None
        return decrypt_secret(host.password_encrypted)

    def create_group(self, name: str, kind: str = "custom", description: str | None = None):
        return self.db.groups.create(name=name, kind=kind, description=description)

    def add_host_to_group(self, group_id: int, host_id: int):
        return self.db.groups.add_host(group_id, host_id)

    def group_hosts(self, group_id: int):
        return self.db.groups.hosts(group_id)

    def resolve_targets(self, target_type: str, target_id: int):
        if target_type == "host":
            host = self.get_host(target_id)
            return [host] if host else []

        if target_type == "group":
            return self.group_hosts(target_id)

        raise ValueError(f"Unknown target_type: {target_type}")

    def to_computer(self, host):
        key_path = None
        if getattr(host, "ssh_key_id", None):
            key_row = self.db.ssh_keys.get(host.ssh_key_id)
            if key_row and getattr(key_row, "private_key_path", None):
                key_path = key_row.private_key_path
        return Computer(
            host=f"{host.username}@{host.address}",
            port=str(host.port),
            key_path=key_path,
        )

    def to_computers(self, hosts: Iterable):
        return [self.to_computer(host) for host in hosts]

    def check_host(self, host_id: int) -> dict:
        host = self.get_host(host_id)
        if not host:
            raise ValueError(f"Host {host_id} not found")
        computer = self.to_computer(host)
        result = computer.executor_ssh("echo netrunner-ok")
        is_active = "[ERROR]" not in result and "Error:" not in result and "netrunner-ok" in result
        updates = {"is_active": 1 if is_active else 0}
        if is_active:
            updates["last_seen_at"] = utcnow_iso()
        updated = self.db.hosts.update(host_id, **updates)
        return {
            "id": updated.id,
            "name": updated.name,
            "is_active": bool(updated.is_active),
            "result": result,
        }

    def check_all_hosts(self) -> dict:
        hosts = self.all_hosts()
        active = 0
        for host in hosts:
            try:
                result = self.check_host(host.id)
                if result["is_active"]:
                    active += 1
            except Exception:
                pass
        return {"checked": len(hosts), "active": active}

    async def check_host_async(self, host_id: int) -> dict:
        """Asynchronous version of check_host using asyncio SSH subprocesses."""
        host = self.get_host(host_id)
        if not host:
            raise ValueError(f"Host {host_id} not found")
        computer = self.to_computer(host)
        result = await computer.async_executor_ssh("echo netrunner-ok")
        is_active = "[ERROR]" not in result and "Error:" not in result and "netrunner-ok" in result
        updates = {"is_active": 1 if is_active else 0}
        if is_active:
            updates["last_seen_at"] = utcnow_iso()
        updated = self.db.hosts.update(host_id, **updates)
        return {
            "id": updated.id,
            "name": updated.name,
            "is_active": bool(updated.is_active),
            "result": result,
        }

    async def check_all_hosts_async(self) -> dict:
        """Check all hosts concurrently without blocking the HTTP event loop."""
        hosts = self.all_hosts()
        results = await asyncio.gather(
            *[self.check_host_async(host.id) for host in hosts],
            return_exceptions=True,
        )
        active = 0
        checked = 0
        for result in results:
            if isinstance(result, Exception):
                continue
            checked += 1
            if result.get("is_active"):
                active += 1
        return {"checked": checked, "active": active}


def _resolve_ssh_key(ctx, ssh_key_id: int | None) -> Any:
    db = ctx.db
    if ssh_key_id:
        key = db.ssh_keys.get(ssh_key_id)
    else:
        key = db.ssh_keys.default()
    if not key:
        raise ValueError("SSH-ключ не найден")
    return key


async def _provision_ssh_key(
        ctx,
        username: str,
        address: str,
        port: int,
        password: str,
        ssh_key_id: int | None = None,
) -> None:
    """Копирует выбранный SSH-ключ на удалённый хост через ssh-copy-id с паролем."""
    key = _resolve_ssh_key(ctx, ssh_key_id)
    public_key_path = key.public_key_path
    if not public_key_path:
        raise ValueError("У выбранного SSH-ключа нет публичной части")
    public_key = Path(public_key_path)
    if not public_key.exists():
        raise ValueError(f"Публичный ключ не найден: {public_key_path}")

    ssh_dir = Path.home() / ".ssh"
    ssh_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Pass the provisioning password via the SSHPASS environment variable so it
    # does not appear in the sshpass command line.
    env = {
        **os.environ,
        "HOME": str(Path.home()),
        "TMPDIR": "/tmp",
        "SSHPASS": password,
    }

    # Add the remote host key to known_hosts before attempting ssh-copy-id so
    # StrictHostKeyChecking=yes does not reject the connection.
    from computer.module.executor_ssh import SSH_KNOWN_HOSTS_FILE
    known_hosts_path = SSH_KNOWN_HOSTS_FILE or str(Path.home() / ".ssh" / "known_hosts")
    known_hosts_file = Path(known_hosts_path)
    known_hosts_file.parent.mkdir(parents=True, exist_ok=True)
    known_hosts_file.touch(mode=0o600, exist_ok=True)
    try:
        scan_result = await asyncio.to_thread(
            subprocess.run,
            ["ssh-keyscan", "-H", "-p", str(port), address],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if scan_result.stdout.strip():
            with known_hosts_file.open("a") as kh:
                kh.write(scan_result.stdout)
    except Exception:
        pass  # keyscan failure is non-fatal; ssh-copy-id will report auth error

    # Build ssh-copy-id options manually: BatchMode=yes must be omitted so
    # sshpass can inject the password; StrictHostKeyChecking is safe because
    # we just ran ssh-keyscan above.
    copy_id_opts = [
        "-o", "ConnectTimeout=10",
        "-o", "StrictHostKeyChecking=yes",
        "-o", "LogLevel=ERROR",
        "-o", f"UserKnownHostsFile={known_hosts_path}",
    ]
    cmd = [
        "sshpass",
        "-e",
        "ssh-copy-id",
        "-i",
        str(public_key),
        "-p",
        str(port),
        *copy_id_opts,
        f"{username}@{address}",
    ]
    try:
        result = await asyncio.to_thread(
            subprocess.run,
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
            env=env,
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        raise RuntimeError(f"ssh-copy-id не удалось: {stderr or exc.returncode}") from exc
    except FileNotFoundError as exc:
        raise RuntimeError("Утилита sshpass не установлена") from exc


def _save_ssh_key(name: str, file_data: str) -> Path:
    """Decode base64 key contents and store under /app/keys (or keys/ for non-Docker)."""
    keys_dir = Path("/app/keys")
    if not keys_dir.exists() or not keys_dir.is_dir():
        keys_dir = Path("keys")

    keys_dir.mkdir(parents=True, exist_ok=True)

    base_name = Path(name).name
    if not base_name or base_name in (".", ".."):
        base_name = "uploaded_key"
    target_path = keys_dir / base_name

    counter = 1
    original_path = target_path
    while target_path.exists():
        stem = original_path.stem
        suffix = original_path.suffix
        target_path = original_path.with_name(f"{stem}_{counter}{suffix}")
        counter += 1

    raw = base64.b64decode(file_data)
    target_path.write_bytes(raw)
    target_path.chmod(0o600)
    return target_path


def _generate_ssh_key(
        key_type: str, passphrase: str | None = None
) -> tuple[str, str, str, int]:
    """Generate an SSH key pair and return private PEM, public OpenSSH line, fingerprint and passphrase flag."""
    if key_type == "ed25519":
        private_key = ed25519.Ed25519PrivateKey.generate()
    elif key_type == "rsa":
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    else:
        raise ValueError(f"Unsupported key type: {key_type}")

    if passphrase:
        encryption = BestAvailableEncryption(passphrase.encode("utf-8"))
        has_passphrase = 1
    else:
        encryption = NoEncryption()
        has_passphrase = 0

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.OpenSSH,
        encryption_algorithm=encryption,
    ).decode("utf-8")

    public_key = private_key.public_key()
    public_openssh = public_key.public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH,
    ).decode("utf-8")

    fingerprint = _ssh_fingerprint(public_openssh)
    return private_pem, public_openssh, fingerprint, has_passphrase


def _write_generated_ssh_key(
        name: str, private_pem: str, public_openssh: str
) -> tuple[Path, Path]:
    """Store a generated key pair under /app/keys (or keys/ for non-Docker)."""
    keys_dir = Path("/app/keys")
    if not keys_dir.exists() or not keys_dir.is_dir():
        keys_dir = Path("keys")

    keys_dir.mkdir(parents=True, exist_ok=True)

    safe_name = re.sub(r"[^a-zA-Z0-9_.-]+", "_", name).strip("_.")
    if not safe_name:
        safe_name = "generated_key"
    private_path = keys_dir / safe_name

    counter = 1
    original_path = private_path
    while private_path.exists():
        stem = original_path.stem
        suffix = original_path.suffix
        private_path = original_path.with_name(f"{stem}_{counter}{suffix}")
        counter += 1

    public_path = private_path.with_suffix(".pub")
    private_path.write_text(private_pem, encoding="utf-8")
    private_path.chmod(0o600)
    public_path.write_text(public_openssh + "\n", encoding="utf-8")
    public_path.chmod(0o644)
    return private_path, public_path


def _ssh_fingerprint(public_openssh: str) -> str:
    """Return an OpenSSH-style SHA256 fingerprint for a public key line."""
    parts = public_openssh.split()
    if len(parts) < 2:
        return ""
    blob = base64.b64decode(parts[1])
    digest = hashlib.sha256(blob).digest()
    return "SHA256:" + base64.b64encode(digest).rstrip(b"=").decode("ascii")


async def _run_background(app: web.Application, coro):
    """Schedule a coroutine as a tracked background task."""
    task = asyncio.create_task(coro)
    app["background_tasks"].add(task)
    task.add_done_callback(lambda t: app["background_tasks"].discard(t))