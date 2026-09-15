"""WebTerminal — интерактивный shell к хосту через браузер. Реализовано через
`ssh -tt` в связке с локальным PTY (стандартная библиотека — `pty`/`termios`/
`fcntl`/`asyncio.loop.add_reader`), без внешних пакетов.

Интерактивный shell — самый привилегированный доступ, который вообще есть в
NetRunner, привилегированнее любого отдельного модуля. Доступен суперпользователю
(любой хост) и преподавателю (только машины его кабинетов).
"""

from __future__ import annotations

import asyncio
import fcntl
import json
import os
import pty
import struct
import termios
from pathlib import Path

from aiohttp import web

from computer.module.executor_ssh import KEY_NAME, KEY_PATH, _ssh_common_options
from server.tools import is_teacher, host_visible


def _build_terminal_cmd(host_str: str, port: str, key_path: str | None) -> list[str]:
    key_file = Path(key_path) if key_path else Path(KEY_PATH) / KEY_NAME
    # -tt форсирует выделение псевдотерминала на удалённой стороне, даже если сам
    # процесс NetRunner не подключён к реальному tty (он подключён к нашему PTY).
    # SetEnv TERM=xterm-256color — форсируем тип терминала, чтобы ncurses-приложения
    # (nano, vim, htop, btop) корректно рисовали UI. SetEnv работает без AcceptEnv
    # в sshd_config (требует OpenSSH ≥ 7.8, что выполняется на любом современном дистрибутиве).
    return [
        "ssh", "-tt",
        "-p", str(port),
        "-o", "SetEnv=TERM=xterm-256color",
        *_ssh_common_options(),
        "-i", str(key_file),
        host_str,
    ]


async def api_terminal_ws(request: web.Request) -> web.WebSocketResponse:
    user = request.get("auth_user")
    ctx = request.app["ctx"]
    host_id = int(request.query.get("host_id", "0") or "0")
    host = ctx.db.hosts.get(host_id)
    if not host:
        raise web.HTTPNotFound(reason="Хост не найден")

    # Суперпользователю доступен терминал любого хоста; преподавателю — только
    # машин его кабинетов; остальным ролям терминал закрыт.
    allowed = bool(user) and (
        user.get("is_superuser")
        or (is_teacher(user) and host_visible(ctx.db, user, host_id))
    )
    if not allowed:
        raise web.HTTPForbidden(reason="Нет доступа к терминалу этого хоста")

    computer = ctx.host_service.to_computer(host)
    cmd = _build_terminal_cmd(computer.host, computer.port, computer.key_path)

    ws = web.WebSocketResponse()
    await ws.prepare(request)

    master_fd, slave_fd = pty.openpty()
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdin=slave_fd, stdout=slave_fd, stderr=slave_fd, close_fds=True,
        )
    except Exception as exc:  # noqa: BLE001
        os.close(master_fd)
        os.close(slave_fd)
        await ws.send_str(json.dumps({"type": "output", "data": f"[ERROR] {exc}\r\n"}))
        await ws.close()
        return ws
    os.close(slave_fd)  # дочерний процесс уже унаследовал — родителю больше не нужен

    loop = asyncio.get_event_loop()

    def _on_master_readable() -> None:
        try:
            data = os.read(master_fd, 4096)
        except OSError:
            data = b""
        if not data:
            try:
                loop.remove_reader(master_fd)
            except Exception:  # noqa: BLE001
                pass
            asyncio.ensure_future(ws.close())
            return
        asyncio.ensure_future(
            ws.send_str(json.dumps({"type": "output", "data": data.decode("utf-8", errors="replace")}))
        )

    loop.add_reader(master_fd, _on_master_readable)

    try:
        async for msg in ws:
            if msg.type != web.WSMsgType.TEXT:
                continue
            try:
                data = json.loads(msg.data)
            except Exception:
                continue
            mtype = data.get("type")
            if mtype == "input":
                try:
                    os.write(master_fd, str(data.get("data", "")).encode("utf-8"))
                except OSError:
                    break
            elif mtype == "resize":
                try:
                    cols = int(data.get("cols", 80))
                    rows = int(data.get("rows", 24))
                    fcntl.ioctl(master_fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
                except (OSError, ValueError, TypeError):
                    pass
    finally:
        try:
            loop.remove_reader(master_fd)
        except Exception:  # noqa: BLE001
            pass
        try:
            proc.kill()
        except Exception:  # noqa: BLE001
            pass
        try:
            os.close(master_fd)
        except OSError:
            pass
    return ws
