"""Окна приложений на рабочем столе хоста: список с иконками и закрытие.

Сама работа — в `desktop_windows_helper.py`, который уходит на хост через stdin
SSH и исполняется python3 от имени пользователя графической сессии. Здесь —
только поиск этой сессии, запуск и разбор ответа.

Требования к хосту те же, что у снимков экрана: X11-сессия (на Wayland
окна чужого клиента недоступны) и sudo без пароля у SSH-пользователя, чтобы
выполнить хелпер от имени владельца сессии.
"""

from __future__ import annotations

import json
from pathlib import Path

_HELPER_SOURCE = (Path(__file__).parent / "desktop_windows_helper.py").read_text(encoding="utf-8")

# Та же схема поиска сессии, что в screenshot_service: активная X11-сессия
# класса user с дисплеем. NO_SESSION / NO_SUDO — сентинелы для понятной ошибки.
_REMOTE_TEMPLATE = """
SESSDATA=""
for s in $(loginctl list-sessions --no-legend 2>/dev/null | awk '{{print $1}}'); do
  eval "$(loginctl show-session "$s" -p Class -p Type -p Display -p Name -p State 2>/dev/null)"
  if [ "$Class" = "user" ] && [ "$Type" = "x11" ] && [ "$State" = "active" ] && [ -n "$Display" ]; then
    SESSDATA="$Name $Display"
    break
  fi
done
if [ -z "$SESSDATA" ]; then echo NO_SESSION; exit 0; fi
set -- $SESSDATA
NR_USER="$1"; NR_DISPLAY="$2"
if [ "$(id -un)" = "$NR_USER" ]; then
  DISPLAY="$NR_DISPLAY" XAUTHORITY="/home/$NR_USER/.Xauthority" python3 - {args}
elif sudo -n true 2>/dev/null; then
  sudo -n -u "$NR_USER" env DISPLAY="$NR_DISPLAY" XAUTHORITY="/home/$NR_USER/.Xauthority" python3 - {args}
else
  echo NO_SUDO
fi
""".strip()

_SENTINEL_ERRORS = {
    "NO_SESSION": "На компьютере нет активной графической сессии (никто не вошёл, экран блокировки или Wayland)",
    "NO_SUDO": "Нет sudo без пароля у пользователя подключения — включите режим исполнения «Сервисный (netrunner-svc)»",
}


class DesktopWindowsError(Exception):
    """Ошибка, которую можно показать пользователю как есть."""


async def _run(computer, args: str) -> dict:
    raw = await computer.async_executor_ssh(_REMOTE_TEMPLATE.format(args=args), input_data=_HELPER_SOURCE)
    text = (raw or "").strip()
    if text.startswith("[ERROR]"):
        raise DesktopWindowsError(f"Не удалось подключиться к компьютеру: {text.splitlines()[0]}")
    for line in reversed(text.splitlines()):
        line = line.strip()
        if line in _SENTINEL_ERRORS:
            raise DesktopWindowsError(_SENTINEL_ERRORS[line])
        if line.startswith("{"):
            try:
                data = json.loads(line)
            except ValueError:
                break
            if not data.get("ok"):
                raise DesktopWindowsError(data.get("error") or "Неизвестная ошибка на компьютере")
            return data
    raise DesktopWindowsError("Компьютер вернул непонятный ответ (нет python3 или libX11?)")


async def list_windows(computer) -> list[dict]:
    return (await _run(computer, "list"))["windows"]


async def close_window(computer, window_id: int, force: bool = False) -> dict:
    return await _run(computer, f"close {int(window_id)}" + (" force" if force else ""))
