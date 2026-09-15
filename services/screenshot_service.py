"""Снимки рабочего стола хостов — превью для профиля/списка хостов.

Один файл на хост (`data/screenshots/host_{id}.jpg`), каждый новый снимок
перезаписывает предыдущий — истории снимков нет, только «текущее состояние».

## Как это устроено

Сервер НЕ открывает никакого нового порта/эндпоинта на хосте и НЕ трогает
report-only endpoint-агента (`agent/netrunner_agent.py`) — у него в коде
структурно нет пути от входящего сообщения до исполнения (см. `agent/README.md`).
Вместо этого снимок делается через уже существующий доверенный канал —
тот же SSH, которым сервер выполняет любой модуль (`to_computer`/
`async_executor_ssh`). Никакого нового attack surface на хосте не появляется.

Один SSH-вызов делает всё за раз (детект сессии → захват → ресайз → base64 в
stdout), декодируется на сервере — не нужен отдельный `scp`-раунд:

1. `loginctl` находит активную **графическую** сессию на seat0 (`Class=user`,
   `Type=x11`, `State=active`) — способ независим от DE (Cinnamon/MATE/...),
   не нужно гадать по именам процессов сессии.
2. Если графической сессии нет (экран блокировки/никто не залогинен) —
   команда возвращает сентинел `NO_SESSION`, снимок не делается (не путаем
   пользователя картинкой экрана блокировки вместо рабочего стола).
3. `scrot` снимает экран **от имени реального пользователя сессии**
   (`sudo -u <user>`) с его `DISPLAY`/`XAUTHORITY` — так не нужно возиться с
   правами на чужой `~/.Xauthority` (обычно 600, чужому пользователю недоступен).
4. `convert` (ImageMagick) сразу на хосте масштабирует весь экран целиком в
   целевой размер, сохраняя пропорции (без кропа); если соотношение сторон
   экрана не совпадает с целевым — добавляются чёрные поля (letterbox), так что
   виден ВЕСЬ рабочий стол, ничего не обрезается. По сети идёт уже маленький
   JPEG, а не полноразмерный скрин произвольного разрешения хоста.
5. `base64 -w0` — весь файл одной строкой в stdout, сервер декодирует.

Требует на хосте: `scrot`, `imagemagick` (`convert`), `loginctl` (systemd-logind,
есть почти везде на современных дистрибутивах). Ориентир — Linux Mint (Cinnamon,
X11); Wayland-сессии (`Type=wayland`) пока не поддерживаются — `scrot` не умеет
снимать Wayland-компоситоры без отдельного протокола.

Проверено вживую на тестовом хосте (без физического монитора — X всё равно
поднимает виртуальный кадровый буфер, отдельный virtual-display не понадобился).
"""

from __future__ import annotations

import base64
import binascii
import shlex
from pathlib import Path

import config
from database.repos.base import utcnow_iso
from services.logger import Logger

logger = Logger()

_SENTINELS = {"NO_SESSION", "CAPTURE_FAILED", "CONVERT_FAILED"}

# Таймаут на один снимок: захват+ресайз на хосте — операция быстрая (доли
# секунды), запас на медленный/перегруженный хост, не на сеть в целом.
CAPTURE_TIMEOUT_SEC = 20


def _build_capture_command(width: int, height: int, quality: int) -> str:
    """Remote-скрипт: детект активной X11-сессии → scrot → convert → base64.

    Каждый шаг молча завершается сентинелом при неудаче — ни одна ветка не
    должна уронить весь однострочник (`set -e` намеренно НЕ используется:
    хотим дифференцированный сентинел, а не голый ненулевой exit code).
    """
    geometry = f"{width}x{height}"
    return f"""
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
NR_PNG="/tmp/.nr_shot_$$.png"
NR_JPG="/tmp/.nr_shot_$$.jpg"
sudo -u "$NR_USER" env DISPLAY="$NR_DISPLAY" XAUTHORITY="/home/$NR_USER/.Xauthority" scrot -q 80 -o "$NR_PNG" >/dev/null 2>&1
if [ ! -s "$NR_PNG" ]; then sudo -u "$NR_USER" rm -f "$NR_PNG" 2>/dev/null; echo CAPTURE_FAILED; exit 0; fi
convert "$NR_PNG" -resize {shlex.quote(geometry)} -background black -gravity center -extent {shlex.quote(geometry)} -quality {int(quality)} "$NR_JPG" >/dev/null 2>&1
sudo -u "$NR_USER" rm -f "$NR_PNG" 2>/dev/null
if [ ! -s "$NR_JPG" ]; then rm -f "$NR_JPG" 2>/dev/null; echo CONVERT_FAILED; exit 0; fi
base64 -w0 "$NR_JPG"
rm -f "$NR_JPG" 2>/dev/null
""".strip()


class ScreenshotService:
    """Снятие и хранение превью рабочего стола хостов."""

    def __init__(self, db, host_service, settings):
        self.db = db
        self.host_service = host_service
        self.settings = settings
        self._dir = Path(config.SCREENSHOTS_PATH)
        self._dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, host_id: int) -> Path:
        return self._dir / f"host_{host_id}.jpg"

    async def capture_host(self, host) -> bool:
        """Снимает и сохраняет превью для одного хоста.

        Возвращает True при успехе. Любая неудача (нет сессии, scrot/convert
        не смогли, SSH недоступен) — тихо False с записью в лог; хост просто
        остаётся с прежним/отсутствующим превью до следующего тика.
        """
        cfg = self.settings.get_config()
        cmd = _build_capture_command(cfg["width"], cfg["height"], cfg["jpeg_quality"])
        computer = self.host_service.to_computer(host)
        try:
            import asyncio
            raw = await asyncio.wait_for(computer.async_executor_ssh(cmd), timeout=CAPTURE_TIMEOUT_SEC)
        except Exception as exc:  # noqa: BLE001 — таймаут/обрыв соединения и т.п.
            logger.warning("Screenshot: SSH-вызов на host_id=%s не удался: %s", host.id, exc)
            return False

        output = raw.strip()
        if not output or output.startswith("[ERROR]") or output in _SENTINELS:
            if output and output not in _SENTINELS:
                logger.warning("Screenshot: host_id=%s вернул ошибку SSH: %s", host.id, output.splitlines()[0])
            return False

        try:
            image_bytes = base64.b64decode(output, validate=True)
        except (binascii.Error, ValueError) as exc:
            logger.warning("Screenshot: host_id=%s вернул невалидный base64: %s", host.id, exc)
            return False
        if not image_bytes:
            return False

        target = self.path_for(host.id)
        try:
            target.write_bytes(image_bytes)
        except OSError as exc:
            logger.warning("Screenshot: не удалось записать файл для host_id=%s: %s", host.id, exc)
            return False

        self.db.hosts.update(
            host.id,
            screenshot_path=str(target),
            screenshot_captured_at=utcnow_iso(),
        )
        return True
