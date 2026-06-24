from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Iterable

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
