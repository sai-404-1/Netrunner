"""Смена пароля учётной записи на хосте (по умолчанию — первичного пользователя).

Bespoke run_for_host (не CommandModule): после смены пароля на самой машине нужно
ещё синхронизировать сохранённый (зашифрованный) пароль в карточке хоста — иначе
следующий sudo-прайминг или переустановка ключа пойдут по старому паролю.

Зачем это вообще нужно (см. netrunner-ip-identity-and-agent-resilience в вики):
первичный пользователь машин кабинетов — обычно `rmk`, пароль у него известен
студентам, и они могут, например, выключить sshd, зная его. От root это не
защищает (сменить пароль обратно себе может любой, у кого уже есть sudo), но
даёт администратору быстрый способ восстановить эксклюзивный контроль здесь и
сейчас, не выходя физически к машине.

Пароль генерируется на сервере (secrets.token_urlsafe — только буквы/цифры/`-`/`_`,
без символов, которые могли бы что-то значить для shell) и уходит на хост только
через stdin heredoc, никогда как аргумент командной строки (`ps` на хосте его не
покажет). В вывод задачи (и, следовательно, в task_runs/историю) пароль не
попадает — он либо сразу шифруется и сохраняется в карточке хоста, либо (если
меняли не первичного пользователя) остаётся только в памяти процесса и теряется.
"""

from __future__ import annotations

import json
import secrets
import shlex


def _new_password(length: int) -> str:
    # token_urlsafe(n) даёт ~1.3*n символов алфавита [A-Za-z0-9_-] — берём с
    # запасом и обрезаем до точной длины.
    return secrets.token_urlsafe(length)[:length]


class UserModule:
    slug = "rotate_password"
    admin_only = True
    supports_task_runner = True

    schema = {
        "placeholders": [
            ["username", "Пользователь (пусто = первичный пользователь хоста)", "", "text"],
            ["length", "Длина пароля", "24", "select",
             [["16", "16"], ["20", "20"], ["24", "24"], ["32", "32"]]],
        ]
    }

    def __init__(self):
        self.title = "Смена пароля пользователя"
        self.description = (
            "Генерирует случайный пароль и меняет его на хосте через sudo chpasswd. "
            "Если пользователь не указан явно — берётся первичный пользователь хоста "
            "(тот, что был при добавлении машины); в этом случае новый пароль сразу "
            "сохраняется в карточке хоста (зашифрованным), для остальных — нет. "
            "Сам пароль нигде не показывается и не попадает в историю запусков. "
            "Не помогает, если у пользователя уже есть sudo и он знает, что его "
            "поменяли — это средство восстановления контроля, а не защита от root."
        )

    async def run_for_host(self, context, host, **kwargs):
        base = {
            "host_id": host.id,
            "name": host.name,
            "address": host.address,
            "port": host.port,
            "username": host.username,
        }

        username = str(kwargs.get("username") or "").strip() or host.username
        try:
            length = max(12, min(64, int(kwargs.get("length") or 24)))
        except (TypeError, ValueError):
            length = 24
        is_primary = username == host.username

        new_password = _new_password(length)

        host_password = None
        hsvc = getattr(context, "host_service", None)
        if hsvc is not None and hasattr(hsvc, "get_host_password"):
            try:
                host_password = hsvc.get_host_password(host.id)
            except Exception:  # noqa: BLE001
                host_password = None
        # Прайминг тем же паролем, что уже сохранён (ещё старым — он в силе, пока
        # chpasswd не отработал), тот же паттерн, что у agent_provision.
        sudo_prime = "sudo -S -v -p '' 2>/dev/null\n" if host_password else ""
        stdin_data = (host_password + "\n") if host_password else None

        remote_script = f"""set -e
{sudo_prime}printf '%s:%s\\n' {shlex.quote(username)} {shlex.quote(new_password)} | sudo chpasswd
echo "Пароль пользователя {shlex.quote(username)} изменён"
"""

        computer = None
        if hsvc is not None and hasattr(hsvc, "to_computer_bootstrap"):
            computer = hsvc.to_computer_bootstrap(host)
        if computer is None:
            from computer import Computer as _C
            computer = _C(host=f"{host.username}@{host.address}", port=str(host.port))

        output = await computer.async_executor_ssh(remote_script, input_data=stdin_data)
        status = "error" if output.startswith("[ERROR]") else "success"

        if status == "success":
            if is_primary and hsvc is not None and hasattr(hsvc, "set_host_password"):
                hsvc.set_host_password(host.id, new_password)
                output += "\nНовый пароль сохранён в карточке хоста."
            elif not is_primary:
                output += (
                    "\nЭто не первичный пользователь хоста — новый пароль нигде не "
                    "сохранён, при следующей смене его нужно будет знать заранее."
                )
            db = getattr(context, "db", None)
            if db is not None and hasattr(db, "host_events"):
                db.host_events.record(
                    host.id,
                    "password_rotated",
                    payload_json=json.dumps({"username": username}, ensure_ascii=False),
                )

        return {**base, "status": status, "output": output}


CustomModule = UserModule()
from . import Modules
Modules.add_update(CustomModule.title, CustomModule)
