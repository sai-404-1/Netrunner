"""Установка/переустановка report-only endpoint-агента на хост (см. agent/README.md).

Bespoke run_for_host (не CommandModule): нужно сначала сгенерировать секреты через
AgentService (SSH-ключ выделенного сервисного пользователя + bearer-токен для WS —
разные секреты для разных целей), потом одним SSH-вызовом через уже существующий
канал — создать пользователя, разложить файлы через heredoc'и (тот же паттерн, что
modules/sound_pinger.py и modules/desktop_style_reset.py) и включить systemd-юнит.
НЕ отключает обычный SSH-доступ (без немедленного отключения остальных, чтобы не
было лок-аута).

ВАЖНО про пользователя, из-под которого выполняется установка: модуль ВСЕГДА
подключается к хосту под ПЕРВИЧНЫМ пользователем (host.username — тот, что был при
добавлении машины, у него есть passwordless sudo). Через него создаётся/чинится
sudoers-правило для netrunner-svc (NOPASSWD: ALL) и ставится агент. Затем фокус
исполнения смещается с первичного пользователя на netrunner-svc: после установки
все повседневные команды NetRunner идут под netrunner-svc (to_computer выбирает
его, если агент провижен). Это нужно в т.ч. для машин, провиженных СТАРОЙ версией
модуля, где netrunner-svc есть, но sudoers-правила для него НЕТ — переустановка
чинит sudoers через первичного пользователя.

Повторный запуск на уже провиженном хосте НЕ ротирует ключ/токен netrunner-svc
(иначе живой WS-агент потеряет соединение: он хранит старый токен в config.json
на хосте, а сервер после provision() знал бы только новый) — обновляются файлы,
юнит и sudoers. Ключ/токен генерируются только когда агента ещё нет.
"""

from __future__ import annotations

import json
import shlex
from pathlib import Path

from . import Modules

_AGENT_DIR = Path(__file__).resolve().parent.parent.parent / "agent"
_AGENT_SCRIPT_PATH = _AGENT_DIR / "netrunner_agent.py"
_SERVICE_UNIT_PATH = _AGENT_DIR / "netrunner-agent.service"


def _resolve_agent_ws_url(explicit: str, db=None) -> str:
    """WS-адрес для конфига агента: аргумент запуска > настройка из
    Администрирования > env > автоопределение (см. _default_agent_ws_url)."""
    value = (explicit or "").strip()
    if value:
        return value
    from server.domens.websocket import _default_agent_ws_url

    return _default_agent_ws_url(db)


class UserModule:
    slug = "agent_provision"
    admin_only = True
    supports_task_runner = True

    schema = {
        "placeholders": [
            ["server_ws_url", "WS-адрес сервера NetRunner (пусто = из Администрирования)",
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
            "passwordless sudo у ПЕРВИЧНОГО пользователя хоста (host.username). "
            "ВАЖНО про адрес сервера: порт бэкенда (8000) не экспонирован из "
            "контейнера — агент не может подставить относительный путь, поэтому URL "
            "должен идти через порт Next.js (3001 в Docker) и префикс /api/python/, "
            "например ws://SERVER_IP:3001/api/python/agent/ws. Повторный запуск = "
            "переустановка: чинит sudoers для netrunner-svc, обновляет файлы и юнит, "
            "ключ/токен не ротирует."
        )

    async def run_for_host(self, context, host, **kwargs):
        base = {
            "host_id": host.id,
            "name": host.name,
            "address": host.address,
            "port": host.port,
            "username": host.username,
        }

        server_ws_url = _resolve_agent_ws_url(
            str(kwargs.get("server_ws_url") or ""), getattr(context, "db", None)
        )
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
            # Переустановка: netrunner-svc уже есть. Ключ/токен НЕ ротируем.
            ssh_username = existing.ssh_username
            public_key = existing.public_key
            token = None  # оставляем прежний (encrypted хранится в existing)
        else:
            # Первая установка: генерим секреты.
            secrets_data = agent_svc.provision(host.id)
            ssh_username = secrets_data["ssh_username"]
            public_key = secrets_data["public_key"]
            token = secrets_data["token"]

        if token is not None:
            config_token = token
        elif existing:
            config_token = existing.token_encrypted
        else:
            config_token = ""
        config_json = json.dumps({
            "host_id": host.id,
            "token": config_token,
            "server_ws_url": server_ws_url,
        })

        # Блок создания пользователя включается всегда: bash-guard «if ! id ...»
        # делает его идемпотентным — при повторной установке просто пропустится,
        # при переустановке на переформатированную машину (юзер пропал, запись в DB
        # осталась) — восстановит пользователя до chown в pubkey_block.
        create_user_block = f"""if ! id {shlex.quote(ssh_username)} >/dev/null 2>&1; then
  sudo useradd -m -s /bin/bash {shlex.quote(ssh_username)}
  sudo mkdir -p /home/{ssh_username}/.ssh
  sudo touch /home/{ssh_username}/.ssh/authorized_keys
  sudo chown -R {shlex.quote(ssh_username)}:{shlex.quote(ssh_username)} /home/{ssh_username}/.ssh
  sudo chmod 700 /home/{ssh_username}/.ssh
  sudo chmod 600 /home/{ssh_username}/.ssh/authorized_keys
fi
"""
        # (блок выше включён безусловно — идемпотентен через «if ! id»)

        # Публичный ключ пишется ВСЕГДА: если юзер был пересоздан / ключ сменился —
        # он должен попасть на хост. Директория .ssh создаётся здесь, а не только в
        # create_user_block: при переустановке (create_user=False) home/.ssh могли
        # отсутствовать на диске (хост был недоступен во время первой провизии —
        # запись в host_agents появилась, а файлы не легли). Без mkdir -p tee падает
        # с «Нет такого файла или каталога» и весь remote_script валится по set -e.
        pubkey_block = f"""
# Публичный ключ сервисного пользователя (вход по ключу, без пароля).
sudo mkdir -p /home/{ssh_username}/.ssh
sudo tee /home/{ssh_username}/.ssh/authorized_keys > /dev/null << 'PUBKEY_EOF'
{public_key}
PUBKEY_EOF
sudo chown -R {shlex.quote(ssh_username)}:{shlex.quote(ssh_username)} /home/{ssh_username}/.ssh
sudo chmod 700 /home/{ssh_username}/.ssh
sudo chmod 600 /home/{ssh_username}/.ssh/authorized_keys
"""

        # sudoers создаётся/чинится ВСЕГДА — это и есть «смещение фокуса» с первичного
        # пользователя на netrunner-svc (для старых хостов, где sudoers нет).
        sudoers_block = f"""
# Полномочия уровня root для сервисного пользователя через sudoers.d.
sudo tee /etc/sudoers.d/{shlex.quote(ssh_username)} > /dev/null << 'SUDOERS_EOF'
{shlex.quote(ssh_username)} ALL=(ALL) NOPASSWD: ALL
SUDOERS_EOF
sudo chmod 0440 /etc/sudoers.d/{shlex.quote(ssh_username)}
sudo chown root:root /etc/sudoers.d/{shlex.quote(ssh_username)}
"""

        # Прайминг sudo паролем хоста: на машинах, где у первичного пользователя
        # НЕТ passwordless sudo, голый `sudo` в скрипте падает («a terminal is
        # required to read the password»). Если пароль хоста сохранён — разово
        # валидируем и кешируем sudo-креды через `sudo -S -v` (пароль подаётся на
        # stdin ssh-канала, НЕ в командную строку — не светится в `ps`), дальше
        # все sudo в скрипте берут из кеша. Если пароль не сохранён или у юзера
        # NOPASSWD — ведём себя как раньше (прайминг не мешает: при NOPASSWD sudo
        # не читает stdin). set -e поймает неудачу прайминга (неверный пароль и
        # нет NOPASSWD) как [ERROR] — тихого «успеха» не будет.
        host_password = None
        hsvc_pw = getattr(context, "host_service", None)
        if hsvc_pw is not None and hasattr(hsvc_pw, "get_host_password"):
            try:
                host_password = hsvc_pw.get_host_password(host.id)
            except Exception:  # noqa: BLE001
                host_password = None
        sudo_prime = "sudo -S -v -p '' 2>/dev/null\n" if host_password else ""
        stdin_data = (host_password + "\n") if host_password else None

        remote_script = f"""set -e
{sudo_prime}{create_user_block}
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
  sudo apt-get install -y python3-websockets >/dev/null 2>&1 \\
    || sudo PIP_ROOT_USER_ACTION=ignore python3 -m pip install --break-system-packages --quiet websockets \\
    || echo "[WARN] Не удалось установить пакет websockets - установите вручную"
fi

# Пакеты для снимков рабочего стола (screenshot_service).
MISSING_PKGS=""
command -v scrot    >/dev/null 2>&1 || MISSING_PKGS="$MISSING_PKGS scrot"
command -v convert  >/dev/null 2>&1 || MISSING_PKGS="$MISSING_PKGS imagemagick"
if [ -n "$MISSING_PKGS" ]; then
  sudo apt-get install -y $MISSING_PKGS >/dev/null 2>&1 \\
    || echo "[WARN] Не удалось установить$MISSING_PKGS — снимки рабочего стола могут не работать"
fi

sudo systemctl daemon-reload
sudo systemctl enable --now netrunner-agent.service
echo "Агент установлен и запущен ({ssh_username}, report-only)."
"""

        # ВСЕГДА подключаемся под ПЕРВИЧНЫМ пользователем (у него passwordless sudo,
        # и именно через него мы чиним sudoers для netrunner-svc).
        hsvc = getattr(context, "host_service", None)
        computer = None
        if hsvc is not None and hasattr(hsvc, "to_computer_bootstrap"):
            computer = hsvc.to_computer_bootstrap(host)
        else:
            from computer import Computer as _C
            computer = _C(host=f"{host.username}@{host.address}", port=str(host.port))

        output = await computer.async_executor_ssh(remote_script, input_data=stdin_data)
        status = "error" if output.startswith("[ERROR]") else "success"
        return {**base, "status": status, "output": output, "is_reinstall": existing is not None}


CustomModule = UserModule()
Modules.add_update(CustomModule.title, CustomModule)
