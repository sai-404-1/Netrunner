"""Установка/переустановка report-only endpoint-агента на хост (см. agent/README.md).

Bespoke run_for_host (не CommandModule): нужно сначала сгенерировать секреты через
AgentService (SSH-ключ выделенного сервисного пользователя + bearer-токен для WS —
разные секреты для разных целей), потом одним SSH-вызовом через уже существующий
канал — создать пользователя, разложить файлы через heredoc'и (тот же паттерн, что
modules/sound_pinger.py и modules/desktop_style_reset.py) и включить systemd-юнит.
НЕ отключает обычный SSH-доступ (без немедленного отключения остальных, чтобы не
было лок-аута).

Переустановка (обновление уже стоящего агента): при повторном запуске модуль
ЗАХОДИТ НА ХОСТ ПОД САМИМ netrunner-svc (его ключ уже провижен и сохранён в
host_agents), перезаписывает скрипт/юнит/конфиг и перезапускает systemd-юнит.
При этом:
- sudoers-правило и authorized_keys НЕ пересоздаются (они уже есть),
- ключ/токен НЕ ротируются (иначе живой WS-агент потеряет соединение навсегда:
  он хранит старый токен в config.json на хосте, а сервер после provision()
  знал бы только новый),
- WS-адрес берётся из аргумента, либо из env NETRUNNER_AGENT_WS_URL, либо
  автоопределяется (тот же порядок, что у _auto_install_agent).
Первичный SSH-пользователь хоста (host.username) используется ТОЛЬКО как bootstrap
при ПЕРВОЙ установке (когда netrunner-svc ещё нет) — дальше общение идёт через
netrunner-svc.
"""

from __future__ import annotations

import json
import os
import shlex
from pathlib import Path

from . import Modules

_AGENT_DIR = Path(__file__).resolve().parent.parent.parent / "agent"
_AGENT_SCRIPT_PATH = _AGENT_DIR / "netrunner_agent.py"
_SERVICE_UNIT_PATH = _AGENT_DIR / "netrunner-agent.service"


def _resolve_agent_ws_url(explicit: str) -> str:
    """WS-адрес для конфига агента: аргумент > env > автоопределение."""
    value = (explicit or "").strip()
    if value:
        return value
    env_url = os.environ.get("NETRUNNER_AGENT_WS_URL", "").strip()
    if env_url:
        return env_url
    from server.domens.websocket import _default_agent_ws_url

    return _default_agent_ws_url()


class UserModule:
    slug = "agent_provision"
    admin_only = True
    supports_task_runner = True

    schema = {
        "placeholders": [
            ["server_ws_url", "WS-адрес сервера NetRunner (пусто = авто)",
             "", "text"],
        ]
    }

    def __init__(self):
        self.title = "Установка/переустановка endpoint-агента"
        self.description = (
            "Создаёт выделенного SSH-пользователя (netrunner-svc, без пароля, только "
            "по ключу) и report-only агента: он сам открывает исходящее WebSocket-"
            "соединение к серверу и держит его постоянно, с автопереподключением — "
            "шлёт только статусы (online при старте/загрузке хоста, heartbeat раз в "
            "минуту), никогда не принимает и не выполняет команды с сервера. НЕ "
            "отключает обычный SSH-доступ хоста (чтобы не было лок-аута). Требует "
            "passwordless sudo у SSH-пользователя хоста (создание пользователя, "
            "systemd-юнит — без tty пароль не ввести). ВАЖНО про адрес сервера: порт "
            "бэкенда (8000) не экспонирован из контейнера — агент, в отличие от "
            "браузера, не может подставить относительный путь, поэтому URL должен "
            "идти через порт Next.js (3001 в Docker) и префикс /api/python/, который "
            "проксируется на бэкенд, например ws://SERVER_IP:3001/api/python/agent/ws "
            "— не ws://SERVER_IP:8000/agent/ws напрямую. Повторный запуск = "
            "переустановка агента: файлы и юнит обновляются, ключ/токен не ротируются."
        )

    async def run_for_host(self, context, host, **kwargs):
        base = {
            "host_id": host.id,
            "name": host.name,
            "address": host.address,
            "port": host.port,
            "username": host.username,
        }

        server_ws_url = _resolve_agent_ws_url(str(kwargs.get("server_ws_url") or ""))
        if not server_ws_url:
            return {**base, "status": "error", "output": "[ERROR] Не удалось определить WS-адрес сервера"}

        try:
            agent_script = _AGENT_SCRIPT_PATH.read_text(encoding="utf-8")
            service_unit = _SERVICE_UNIT_PATH.read_text(encoding="utf-8")
        except OSError as exc:
            return {**base, "status": "error", "output": f"[ERROR] Не удалось прочитать файлы агента: {exc}"}

        from services.agent_service import AgentService

        agent_svc = AgentService(context.db)
        existing = agent_svc.get_existing(context.db, host.id)
        if existing:
            # Переустановка: netrunner-svc уже есть. Заходим под НИМ его ключом.
            ssh_username = existing.ssh_username
            public_key = existing.public_key
            is_reinstall = True
            # Ключ не ротируем: живой агент держит старый токен, а authorized_keys
            # на хосте уже содержит этот же public_key.
            token = None
        else:
            # Первая установка: генерим секреты и подключаемся под первичным юзером.
            secrets_data = agent_svc.provision(host.id)
            ssh_username = secrets_data["ssh_username"]
            public_key = secrets_data["public_key"]
            token = secrets_data["token"]
            is_reinstall = False

        # server_ws_url подставляется как есть (уже валидный URL)
        config_json = json.dumps({
            "host_id": host.id,
            "token": token if token is not None else (existing.token_encrypted if existing else ""),
            "server_ws_url": server_ws_url,
        })

        # Собираем remote-скрипт: useradd только если юзера нет (первая установка).
        create_user_block = ""
        if not is_reinstall:
            create_user_block = f"""if ! id {shlex.quote(ssh_username)} >/dev/null 2>&1; then
  sudo useradd -m -s /bin/bash {shlex.quote(ssh_username)}
  sudo mkdir -p /home/{ssh_username}/.ssh
  sudo touch /home/{ssh_username}/.ssh/authorized_keys
  sudo chown -R {shlex.quote(ssh_username)}:{shlex.quote(ssh_username)} /home/{ssh_username}/.ssh
  sudo chmod 700 /home/{ssh_username}/.ssh
  sudo chmod 600 /home/{ssh_username}/.ssh/authorized_keys
fi
"""

        sudoers_block = ""
        if not is_reinstall:
            sudoers_block = f"""
# Полномочия уровня root для сервисного пользователя через sudoers.d.
sudo tee /etc/sudoers.d/{shlex.quote(ssh_username)} > /dev/null << 'SUDOERS_EOF'
{shlex.quote(ssh_username)} ALL=(ALL) NOPASSWD: ALL
SUDOERS_EOF
sudo chmod 0440 /etc/sudoers.d/{shlex.quote(ssh_username)}
sudo chown root:root /etc/sudoers.d/{shlex.quote(ssh_username)}
"""
        pubkey_block = ""
        if not is_reinstall:
            pubkey_block = f"""
# Публичный ключ сервисного пользователя (вход по ключу, без пароля).
sudo tee /home/{ssh_username}/.ssh/authorized_keys > /dev/null << 'PUBKEY_EOF'
{public_key}
PUBKEY_EOF
sudo chown -R {shlex.quote(ssh_username)}:{shlex.quote(ssh_username)} /home/{ssh_username}/.ssh
"""

        remote_script = f"""set -e
{create_user_block}
{pubkey_block}
{sudoers_block}
sudo mkdir -p /etc/netrunner-agent /opt/netrunner-agent
sudo tee /etc/netrunner-agent/config.json > /dev/null << 'CONFIG_EOF'
{config_json}
CONFIG_EOF
sudo chown root:{shlex.quote(ssh_username)} /etc/netrunner-agent/config.json
sudo chmod 640 /etc/netrunner-agent/config.json

sudo tee /opt/netrunner-agent/netrunner_agent.py > /dev/null << 'AGENT_EOF'
{agent_script}
AGENT_EOF

sudo tee /etc/systemd/system/netrunner-agent.service > /dev/null << 'UNIT_EOF'
{service_unit}
UNIT_EOF

if ! python3 -c "import websockets" >/dev/null 2>&1; then
  sudo apt-get install -y python3-websockets >/dev/null 2>&1 \
    || sudo PIP_ROOT_USER_ACTION=ignore python3 -m pip install --break-system-packages --quiet websockets \
    || echo "[WARN] Не удалось установить пакет websockets - установите вручную"
fi

sudo systemctl daemon-reload
sudo systemctl enable --now netrunner-agent.service
echo "Агент установлен и запущен ({ssh_username}, report-only)."
"""

        to_computer = getattr(context, "to_computer", None)
        computer = None
        if callable(to_computer):
            try:
                computer = to_computer(host)
            except Exception:
                computer = None
        if computer is None:
            from computer import Computer
            computer = Computer(host=f"{host.username}@{host.address}", port=str(host.port))

        output = await computer.async_executor_ssh(remote_script)
        status = "error" if output.startswith("[ERROR]") else "success"
        return {**base, "status": status, "output": output, "is_reinstall": is_reinstall}


CustomModule = UserModule()
Modules.add_update(CustomModule.title, CustomModule)
