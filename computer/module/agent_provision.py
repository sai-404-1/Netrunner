"""Установка report-only endpoint-агента на хост (см. agent/README.md).

Bespoke run_for_host (не CommandModule): нужно сначала сгенерировать секреты через
AgentService (SSH-ключ выделенного сервисного пользователя + bearer-токен для WS —
разные секреты для разных целей), потом одним SSH-вызовом через уже существующий
канал — создать пользователя, разложить файлы через heredoc'и (тот же паттерн, что
modules/sound_pinger.py и modules/desktop_style_reset.py) и включить systemd-юнит.
НЕ отключает обычный SSH-доступ (без немедленного отключения остальных, чтобы не
было лок-аута).
"""

from __future__ import annotations

import json
import shlex
from pathlib import Path

from . import Modules

# Импорт AgentService — внутри run_for_host, не на уровне модуля: services/
# импортирует computer (для HostService), а этот файл сам загружается как часть
# computer.module.__init__ при самом первом импорте пакета computer — импорт
# services на верхнем уровне тут ловит circular import.

_AGENT_DIR = Path(__file__).resolve().parent.parent.parent / "agent"
_AGENT_SCRIPT_PATH = _AGENT_DIR / "netrunner_agent.py"
_SERVICE_UNIT_PATH = _AGENT_DIR / "netrunner-agent.service"


class UserModule:
    slug = "agent_provision"
    admin_only = True
    supports_task_runner = True

    schema = {
        "placeholders": [
            ["server_ws_url", "WS-адрес сервера NetRunner",
             "ws://SERVER_IP:3001/api/python/agent/ws", "text"],
        ]
    }

    def __init__(self):
        self.title = "Установка endpoint-агента"
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
            "— не ws://SERVER_IP:8000/agent/ws напрямую."
        )

    async def run_for_host(self, context, host, **kwargs):
        base = {
            "host_id": host.id,
            "name": host.name,
            "address": host.address,
            "port": host.port,
            "username": host.username,
        }

        server_ws_url = str(kwargs.get("server_ws_url") or "").strip()
        if not server_ws_url:
            return {**base, "status": "error", "output": "[ERROR] Не указан WS-адрес сервера"}

        try:
            agent_script = _AGENT_SCRIPT_PATH.read_text(encoding="utf-8")
            service_unit = _SERVICE_UNIT_PATH.read_text(encoding="utf-8")
        except OSError as exc:
            return {**base, "status": "error", "output": f"[ERROR] Не удалось прочитать файлы агента: {exc}"}

        from services.agent_service import AgentService

        agent_svc = AgentService(context.db)
        secrets_data = agent_svc.provision(host.id)
        ssh_username = secrets_data["ssh_username"]
        public_key = secrets_data["public_key"]
        config_json = json.dumps({
            "host_id": host.id,
            "token": secrets_data["token"],
            "server_ws_url": server_ws_url,
        })

        remote_script = f"""set -e
if ! id {shlex.quote(ssh_username)} >/dev/null 2>&1; then
  sudo useradd -m -s /bin/bash {shlex.quote(ssh_username)}
  sudo mkdir -p /home/{ssh_username}/.ssh
  sudo touch /home/{ssh_username}/.ssh/authorized_keys
  sudo chown -R {shlex.quote(ssh_username)}:{shlex.quote(ssh_username)} /home/{ssh_username}/.ssh
  sudo chmod 700 /home/{ssh_username}/.ssh
  sudo chmod 600 /home/{ssh_username}/.ssh/authorized_keys
fi

# Публичный ключ сервисного пользователя (вход по ключу, без пароля).
sudo tee /home/{ssh_username}/.ssh/authorized_keys > /dev/null << 'PUBKEY_EOF'
{public_key}
PUBKEY_EOF
sudo chown -R {shlex.quote(ssh_username)}:{shlex.quote(ssh_username)} /home/{ssh_username}/.ssh

# Полномочия уровня root для сервисного пользователя через sudoers.d.
sudo tee /etc/sudoers.d/{shlex.quote(ssh_username)} > /dev/null << 'SUDOERS_EOF'
{shlex.quote(ssh_username)} ALL=(ALL) NOPASSWD: ALL
SUDOERS_EOF
sudo chmod 0440 /etc/sudoers.d/{shlex.quote(ssh_username)}
sudo chown root:root /etc/sudoers.d/{shlex.quote(ssh_username)}

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
  sudo apt-get install -y python3-websockets >/dev/null 2>&1 \\
    || sudo PIP_ROOT_USER_ACTION=ignore python3 -m pip install --break-system-packages --quiet websockets \\
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
        return {**base, "status": status, "output": output}


CustomModule = UserModule()
Modules.add_update(CustomModule.title, CustomModule)
