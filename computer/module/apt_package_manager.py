"""APT package manager module for NetRunner.

This module installs or removes Debian/Ubuntu packages via apt over SSH. It
supports per-host concurrent execution, logging through the task context, and
returns a structured record of which packages were installed or removed on each
host.

Supported args:
    action: "install" | "remove" | "update" | "autoremove"
    packages: space-separated package names (required for install/remove)
    sudo_password: optional sudo password for non-root users
"""

from __future__ import annotations

import asyncio
import shlex
from dataclasses import dataclass

from . import Modules


@dataclass
class AptResult:
    host_id: int
    name: str
    address: str
    port: int
    username: str
    action: str
    packages: list[str]
    changed: list[str]
    failed: list[str]
    stdout: str
    stderr: str
    returncode: int


class UserModule:
    slug = "apt_package_manager"
    title = "APT package manager"
    description = "Устанавливает, удаляет или обновляет пакеты APT."
    web_ui_visible = True
    schema = {
        "placeholders": [
            ["action", "Действие", "update", "select", [
                ["update",     "Обновить список пакетов"],
                ["install",    "Установить"],
                ["remove",     "Удалить"],
                ["autoremove", "Автоочистка"],
            ]],
            ["packages",      "Пакеты (через пробел)", "",  "text"],
            ["sudo_password", "Пароль sudo",           "",  "password"],
        ]
    }

    def __init__(self):
        self._ssh_options = None

    def _parse_packages(self, raw: str | list[str] | None) -> list[str]:
        if not raw:
            return []
        if isinstance(raw, list):
            return [p.strip() for p in raw if p and p.strip()]
        return [p.strip() for p in raw.split() if p.strip()]

    def _build_command(self, action: str, packages: list[str], sudo_password: str | None = None) -> str:
        """Build a safe remote shell command."""
        sudo = "sudo -S" if sudo_password else "sudo -n"
        if action == "update":
            remote = f"DEBIAN_FRONTEND=noninteractive {sudo} apt-get update -y"
        elif action == "autoremove":
            remote = f"DEBIAN_FRONTEND=noninteractive {sudo} apt-get autoremove -y"
        elif action in ("install", "remove"):
            if not packages:
                raise ValueError(f"Packages are required for action '{action}'")
            apt_action = "install" if action == "install" else "remove"
            quoted = " ".join(shlex.quote(p) for p in packages)
            remote = f"DEBIAN_FRONTEND=noninteractive {sudo} apt-get {apt_action} -y {quoted}"
        else:
            raise ValueError(f"Unknown action: {action}")

        return remote

    def _make_computer(self, context, host):
        to_computer = getattr(context, "to_computer", None)
        if callable(to_computer):
            try:
                return to_computer(host)
            except Exception:
                pass
        from computer import Computer
        return Computer(host=f"{host.username}@{host.address}", port=str(host.port))

    async def _run_apt(self, computer: Computer, command: str, sudo_password: str | None = None) -> tuple[str, str, int]:
        """Execute the apt command via async SSH and return stdout, stderr, returncode."""
        from computer.module.executor_ssh import _build_ssh_cmd

        cmd = _build_ssh_cmd(computer.host, computer.port, command)
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE if sudo_password else None,
            )
            stdout_b, stderr_b = await proc.communicate(
                input=sudo_password.encode("utf-8") if sudo_password else None
            )
            stdout = stdout_b.decode("utf-8", errors="replace")
            stderr = stderr_b.decode("utf-8", errors="replace")
            return stdout, stderr, proc.returncode
        except Exception as exc:
            return "", f"[ERROR] {exc}", 1

    def _detect_changed(self, action: str, stdout: str, stderr: str) -> list[str]:
        """Heuristic detection of changed packages from apt output."""
        text = f"{stdout}\n{stderr}"
        changed = set()

        if action == "install":
            # Lines like "The following NEW packages will be installed:" followed by package names.
            lines = text.splitlines()
            in_new = False
            for line in lines:
                if "NEW packages will be installed" in line:
                    in_new = True
                    continue
                if in_new:
                    if not line.strip() or line.startswith("The following") or line.startswith("0 upgraded"):
                        in_new = False
                        continue
                    # Package names are space-separated and may wrap with indentation.
                    for pkg in line.split():
                        pkg = pkg.strip()
                        if pkg and pkg not in ("•", "*"):
                            changed.add(pkg)

        elif action == "remove":
            lines = text.splitlines()
            in_remove = False
            for line in lines:
                if "packages will be REMOVED" in line or "package will be REMOVED" in line:
                    in_remove = True
                    continue
                if in_remove:
                    if not line.strip() or line.startswith("The following") or line.startswith("0 upgraded"):
                        in_remove = False
                        continue
                    for pkg in line.split():
                        pkg = pkg.strip()
                        if pkg and pkg not in ("•", "*"):
                            changed.add(pkg)

        elif action in ("update", "autoremove"):
            # For update, report packages that were upgraded.
            for line in text.splitlines():
                if line.startswith("Get:") or line.startswith("Ign:") or line.startswith("Hit:"):
                    parts = line.split()
                    if len(parts) >= 2:
                        changed.add(parts[1].split("/")[-1])

        return sorted(changed)

    def _detect_failed(self, packages: list[str], stdout: str, stderr: str, returncode: int) -> list[str]:
        if returncode == 0:
            return []
        text = f"{stdout}\n{stderr}".lower()
        failed = []
        for pkg in packages:
            if pkg.lower() in text:
                failed.append(pkg)
        return failed

    def _format_output(self, result: AptResult) -> str:
        lines = [
            f"[{result.action.upper()}] {result.name} ({result.username}@{result.address}:{result.port})",
            f"Packages: {', '.join(result.packages) if result.packages else 'n/a'}",
            f"Changed: {', '.join(result.changed) if result.changed else 'none'}",
            f"Failed: {', '.join(result.failed) if result.failed else 'none'}",
            f"Return code: {result.returncode}",
        ]
        if result.stdout.strip():
            lines.append("--- stdout ---")
            lines.append(result.stdout.strip())
        if result.stderr.strip():
            lines.append("--- stderr ---")
            lines.append(result.stderr.strip())
        return "\n".join(lines)

    def run(self, context, targets, **kwargs):
        """Synchronous fallback for non-async contexts."""
        return asyncio.run(self.run_async(context, targets, **kwargs))

    async def run_async(self, context, targets, **kwargs):
        """Run apt on all targets concurrently."""
        tasks = [self.run_for_host(context, host, **kwargs) for host in targets]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        per_host = []
        for host, result in zip(targets, results):
            if isinstance(result, Exception):
                per_host.append({
                    "host_id": host.id,
                    "name": host.name,
                    "address": host.address,
                    "port": host.port,
                    "username": host.username,
                    "status": "error",
                    "output": f"[ERROR] {result}",
                    "action": kwargs.get("action", "install"),
                    "packages": [],
                    "changed": [],
                    "failed": [],
                })
            else:
                per_host.append(result)

        summary = "\n\n".join(
            f"{r['name']}: action={r['action']}, packages={r['packages']}, changed={r['changed']}, failed={r['failed']}"
            for r in per_host
        )
        return {
            "summary_text": summary,
            "per_host_results": per_host,
        }

    async def run_for_host(self, context, host, **kwargs):
        """Per-host async execution used by TaskRunner."""
        action = str(kwargs.get("action") or "install").strip().lower()
        packages = self._parse_packages(kwargs.get("packages"))
        sudo_password = kwargs.get("sudo_password") or None

        logger = getattr(context, "logger", None)
        if logger:
            logger.info(
                "task_run=%s host=%s action=%s packages=%s",
                getattr(context, "task_run_id", None),
                host.name,
                action,
                packages,
            )

        computer = self._make_computer(context, host)

        try:
            command = self._build_command(action, packages, sudo_password)
        except ValueError as exc:
            return {
                "host_id": host.id,
                "name": host.name,
                "address": host.address,
                "port": host.port,
                "username": host.username,
                "status": "error",
                "output": f"[ERROR] {exc}",
                "action": action,
                "packages": packages,
                "changed": [],
                "failed": packages,
            }

        stdout, stderr, returncode = await self._run_apt(computer, command, sudo_password)
        changed = self._detect_changed(action, stdout, stderr)
        failed = self._detect_failed(packages, stdout, stderr, returncode)

        result = AptResult(
            host_id=host.id,
            name=host.name,
            address=host.address,
            port=host.port,
            username=host.username,
            action=action,
            packages=packages,
            changed=changed,
            failed=failed,
            stdout=stdout,
            stderr=stderr,
            returncode=returncode,
        )

        output = self._format_output(result)
        status = "success" if returncode == 0 and not failed else "error"

        if logger:
            logger.info(
                "task_run=%s host=%s action=%s changed=%s failed=%s status=%s",
                getattr(context, "task_run_id", None),
                host.name,
                action,
                changed,
                failed,
                status,
            )

        return {
            "host_id": host.id,
            "name": host.name,
            "address": host.address,
            "port": host.port,
            "username": host.username,
            "status": status,
            "output": output,
            "action": action,
            "packages": packages,
            "changed": changed,
            "failed": failed,
            "returncode": returncode,
        }


CustomModule = UserModule()
Modules.add_update(CustomModule.title, CustomModule)
