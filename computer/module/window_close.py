"""Закрытие окон приложений на рабочем столе хоста.

Находит активную X11-сессию через loginctl (тот же паттерн, что и в
screenshot_service.py) и закрывает окна по имени/подстроке через xdotool.
Используем xdotool (не wmctrl): он ищет через XQueryTree, не зависит от
_NET_CLIENT_LIST — работает в том числе в Cinnamon где этот атрибут может
отсутствовать. Пользователь один — первая активная X11-сессия.

Требует на хосте: xdotool (устанавливается автоматически если нет).
"""

from __future__ import annotations

import shlex

from . import Modules


def _build_close_script(window_name: str, close_all: bool) -> str:
    name_q = shlex.quote(window_name)
    name_q_lower = shlex.quote(window_name.lower())

    if close_all:
        close_block = f"""
WIDS=$(sudo -u "$NR_USER" env DISPLAY="$NR_DISPLAY" XAUTHORITY="/home/$NR_USER/.Xauthority" \\
  xdotool search --name {name_q} 2>/dev/null || true)
COUNT=$(echo "$WIDS" | grep -c '[0-9]' || true)
if [ "$COUNT" -eq 0 ]; then
  echo "Окно {name_q} не найдено"
  exit 0
fi
CLOSED=0
for WID in $WIDS; do
  sudo -u "$NR_USER" env DISPLAY="$NR_DISPLAY" XAUTHORITY="/home/$NR_USER/.Xauthority" \\
    xdotool windowclose "$WID" 2>/dev/null && CLOSED=$(( CLOSED + 1 )) || true
done
echo "Закрыто окон: $CLOSED из $COUNT"
"""
    else:
        close_block = f"""
WID=$(sudo -u "$NR_USER" env DISPLAY="$NR_DISPLAY" XAUTHORITY="/home/$NR_USER/.Xauthority" \\
  xdotool search --name {name_q} 2>/dev/null | head -1 || true)
if [ -z "$WID" ]; then
  echo "Окно {name_q} не найдено"
  exit 0
fi
sudo -u "$NR_USER" env DISPLAY="$NR_DISPLAY" XAUTHORITY="/home/$NR_USER/.Xauthority" \\
  xdotool windowclose "$WID" 2>/dev/null && echo "Окно {name_q} закрыто (id=$WID)" || echo "[WARN] Не удалось закрыть окно $WID"
"""

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
if ! command -v xdotool >/dev/null 2>&1; then
  sudo apt-get install -y xdotool >/dev/null 2>&1 \\
    || {{ echo "[ERROR] xdotool не установлен и не удалось установить автоматически"; exit 1; }}
fi
{close_block.strip()}
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
            "Работает через xdotool и активную X11-сессию пользователя. "
            "Если xdotool не установлен — устанавливается автоматически. "
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

        close_all = str(kwargs.get("close_all") or "false").strip().lower() == "true"
        script = _build_close_script(window_name, close_all)

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
