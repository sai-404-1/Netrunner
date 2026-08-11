"""Модуль массовой рассылки файлов на хосты (только для администратора).

Монолитный встроенный модуль. Пользователь выбирает заранее загруженные файлы
(см. эндпоинты /api/uploads) и каталог назначения на хосте, выбирает цель (хост
или группу) и запускает рассылку. Файлы копируются на каждый хост по очереди через
безопасный scp (аргументы списком, без shell-инъекций), с ключом конкретного хоста.

По хостам рассылка идёт асинхронно, но с ограничением одновременных передач
(см. ``max_parallel`` / ``MAX_PARALLEL_TRANSFERS`` в config) — чтобы не нагружать сеть.
"""

from __future__ import annotations

import asyncio

from . import Modules

try:
    from config import MAX_PARALLEL_TRANSFERS
except Exception:  # pragma: no cover - config всегда есть в рантайме
    MAX_PARALLEL_TRANSFERS = 3


class UserModule:
    slug = "file_distribute"
    title = "Рассылка файлов"
    description = (
        "Массовое копирование загруженных файлов на хост или группу хостов "
        "по scp. Только для администратора."
    )
    # Видимость и запуск только для суперпользователя (см. server/server.py).
    admin_only = True
    web_ui_visible = True
    # Лимит одновременных передач по хостам (читается раннером).
    max_parallel = MAX_PARALLEL_TRANSFERS

    # Схема для страницы запуска. Поле файлов рендерится кастомным UI по slug;
    # здесь объявлен только каталог назначения.
    schema = {
        "placeholders": [
            ["dest_path", "Каталог назначения на хосте", "/tmp", "text"],
        ],
        "ui": "file_distribute",
    }

    def __init__(self):
        pass

    def exec(self):
        print("Этот модуль запускается через систему задач.")

    # ------------------------------------------------------------------
    # Вспомогательное
    # ------------------------------------------------------------------
    def _resolve_key_path(self, context, host) -> str | None:
        """Путь к приватному ключу хоста (или ключу по умолчанию)."""
        db = getattr(context, "db", None)
        if db is None:
            return None
        key_row = None
        if getattr(host, "ssh_key_id", None):
            key_row = db.ssh_keys.get(host.ssh_key_id)
        if key_row is None:
            key_row = db.ssh_keys.default()
        return getattr(key_row, "private_key_path", None) if key_row else None

    def _resolve_files(self, context, file_ids) -> list:
        """Список (original_name, stored_path) по выбранным id."""
        db = getattr(context, "db", None)
        result = []
        if db is None:
            return result
        for fid in file_ids:
            try:
                row = db.uploaded_files.get(int(fid))
            except (TypeError, ValueError):
                row = None
            if row is not None:
                result.append((row.original_name, row.stored_path))
        return result

    async def _run_cmd(self, cmd: list[str], timeout: int = 300):
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise
        out = (stdout or b"").decode("utf-8", "replace")
        err = (stderr or b"").decode("utf-8", "replace")
        return proc.returncode, (out + err).strip()

    def _scp_cmd(self, host, key_path, local_path, remote_target) -> list[str]:
        from computer.module.executor_ssh import _ssh_common_options

        cmd = ["scp", "-P", str(host.port), *_ssh_common_options()]
        if key_path:
            cmd += ["-i", str(key_path)]
        cmd += [local_path, remote_target]
        return cmd

    # ------------------------------------------------------------------
    # Исполнение
    # ------------------------------------------------------------------
    async def run_for_host(self, context, host, **kwargs):
        file_ids = kwargs.get("file_ids") or []
        dest_path = str(kwargs.get("dest_path") or "/tmp").strip() or "/tmp"

        base = {
            "host_id": host.id,
            "name": host.name,
            "address": host.address,
            "port": host.port,
            "username": host.username,
        }

        files = self._resolve_files(context, file_ids)
        if not files:
            return {**base, "status": "error", "output": "[ERROR] Не выбрано ни одного файла"}

        key_path = self._resolve_key_path(context, host)
        target_base = f"{host.username}@{host.address}"

        # Гарантируем существование каталога назначения.
        from computer import Computer

        computer = Computer(host=target_base, port=str(host.port), key_path=key_path)
        try:
            import shlex
            await computer.async_executor_ssh(f"mkdir -p {shlex.quote(dest_path)}")
        except Exception as exc:  # noqa: BLE001 — диагностика, не фатально
            return {**base, "status": "error", "output": f"[ERROR] Не удалось создать каталог {dest_path}: {exc}"}

        lines = []
        failed = 0
        # Файлы отправляются по очереди (последовательно) на этот хост.
        for original_name, stored_path in files:
            remote_target = f"{target_base}:{dest_path.rstrip('/')}/{original_name}"
            cmd = self._scp_cmd(host, key_path, stored_path, remote_target)
            try:
                code, output = await self._run_cmd(cmd)
            except asyncio.TimeoutError:
                failed += 1
                lines.append(f"[FAIL] {original_name}: таймаут передачи")
                continue
            if code == 0:
                lines.append(f"[OK] {original_name} → {dest_path}")
            else:
                failed += 1
                lines.append(f"[FAIL] {original_name}: {output or f'код {code}'}")

        status = "error" if failed else "success"
        summary = (
            f"Отправлено {len(files) - failed} из {len(files)} в {dest_path}\n"
            + "\n".join(lines)
        )
        return {**base, "status": status, "output": ("[ERROR] " if failed else "") + summary}


CustomModule = UserModule()
Modules.add_update(CustomModule.title, CustomModule)
