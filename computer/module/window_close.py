"""Закрытие окон приложений на рабочем столе хоста.

Находит активную X11-сессию через loginctl (тот же паттерн, что и в
screenshot_service.py) и закрывает окна по имени/подстроке через wmctrl.
Пользователь один — первая (и единственная) активная сессия на seat0.

Требует на хосте: wmctrl (`sudo apt-get install wmctrl`).
"""

from __future__ import annotations

import shlex

from . import Modules


def _build_close_script(window_name: str, kill_all: bool) -> str:
    flag = "-a" if not kill_all else ""
    # wmctrl -c закрывает первое совпадение, -c в цикле — все совпадения.
    if kill_all:
        close_cmd = f"wmctrl -l | grep -i {shlex.quote(window_name)} | awk '{{print $1}}' | xargs -I{{}} wmctrl -ic {{}}"
    else:
        close_cmd = f"wmctrl -c {shlex.quote(window_name)}"

    return f"""
SESSDATA=""
for s in $(loginctl list-sessions --no-legend 2>/dev/null | awk '{{print $1}}' | sort -n); do
  eval "$(loginctl show-session "$s" -p Class -p Type -p Display -p Name -p State 2>/dev/null)"
  if [ "$Class" = "user" ] && [ "$Type" = "x11" ] && [ "$State" = "active" ] && [ -n "$Display" ]; then
    SESSDATA="$Name $Display"
    break
  fi
done
if [ -z "$SESSDATA" ]; then
  echo "NO_SESSION: активная X11-сессия не найдена"
  exit 0
fi
set -- $SESSDATA
NR_USER="$1"; NR_DISPLAY="$2"
if ! command -v wmctrl >/dev/null 2>&1; then
  sudo apt-get install -y wmctrl >/dev/null 2>&1 || {{ echo "[ERROR] wmctrl не установлен и не удалось установить автоматически"; exit 1; }}
fi
BEFORE=$(sudo -u "$NR_USER" env DISPLAY="$NR_DISPLAY" XAUTHORITY="/home/$NR_USER/.Xauthority" wmctrl -l 2>/dev/null | grep -ic {shlex.quote(window_name)} || true)
if [ "$BEFORE" -eq 0 ]; then
  echo "Окно '{window_name}' не найдено (уже закрыто или не запущено)"
  exit 0
fi
sudo -u "$NR_USER" env DISPLAY="$NR_DISPLAY" XAUTHORITY="/home/$NR_USER/.Xauthority" {close_cmd} 2>/dev/null || true
sleep 0.5
AFTER=$(sudo -u "$NR_USER" env DISPLAY="$NR_DISPLAY" XAUTHORITY="/home/$NR_USER/.Xauthority" wmctrl -l 2>/dev/null | grep -ic {shlex.quote(window_name)} || true)
CLOSED=$(( BEFORE - AFTER ))
echo "Закрыто окон: $CLOSED из $BEFORE (осталось: $AFTER)"
""".strip()


class WindowCloseModule:
    slug = "window_close"
    admin_only = False
    supports_task_runner = True

    schema = {
        "placeholders": [
            ["window_name", "Имя окна (подстрока)", "Firefox", "text"],
            ["close_all", "Закрыть все совпадения", "false", "radio",
             [["false", "Только первое"], ["true", "Все совпадения"]]],
        ]
    }

    def __init__(self):
        self.title = "Закрытие окна приложения"
        self.description = (
            "Закрывает окно приложения на рабочем столе хоста по имени (подстроке). "
            "Работает через wmctrl и активную X11-сессию пользователя. "
            "Если wmctrl не установлен — устанавливается автоматически. "
            "Возвращает количество закрытых окон."
        )

    async def run_for_host(self, context, host, **kwargs):
        base = {
            "host_id": host.id,
            "name": host.name,
            "address": host.address,
        }
        window_name = str(kwargs.get("window_name") or "").strip()
        if not window_name:
            return {**base, "status": "error", "output": "[ERROR] Укажите имя окна"}

        kill_all = str(kwargs.get("close_all") or "false").strip().lower() == "true"
        script = _build_close_script(window_name, kill_all)

        hsvc = getattr(context, "host_service", None)
        if hsvc is not None and hasattr(hsvc, "to_computer"):
            computer = hsvc.to_computer(host)
        else:
            from computer import Computer as _C
            computer = _C(host=f"{host.username}@{host.address}", port=str(host.port))

        output = await computer.async_executor_ssh(script)
        status = "error" if output.startswith("[ERROR]") else "success"
        return {**base, "status": status, "output": output}


CustomModule = WindowCloseModule()
Modules.add_update(CustomModule.title, CustomModule)
