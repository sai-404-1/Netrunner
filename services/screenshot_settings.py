"""Настройка снимков рабочего стола хостов (превью в UI).

Зачем: администратор должен уметь целиком выключить снятие скриншотов (приватность),
а также подстроить частоту и размер превью под нагрузку сети/сервера. Настройка
живёт в `app_settings` и перечитывается **на каждом тике** фонового цикла
(`server/server.py::_screenshot_loop`), так что правка со страницы
«Администрирование» применяется без перезапуска сервера — тот же принцип, что и
у `execution_settings.py`.
"""

from __future__ import annotations

# Единственный источник правды по настройке: ключ в app_settings, значение по
# умолчанию, границы и подпись для интерфейса.
FIELDS: dict[str, dict] = {
    "enabled": {
        "key": "screenshot_enabled",
        "type": "bool",
        "default": True,
        "label": "Снимки рабочего стола",
        "hint": (
            "Периодически снимать превью рабочего стола хостов для просмотра "
            "администратором/преподавателем. Выключено — превью не собираются "
            "вообще, ни для кого."
        ),
    },
    "interval_seconds": {
        "key": "screenshot_interval_seconds",
        "type": "int",
        "default": 10,
        "min": 3,
        "max": 300,
        "label": "Интервал снимков, с",
        "hint": "Как часто обновлять превью каждого хоста. Каждый новый снимок заменяет предыдущий.",
    },
    "width": {
        "key": "screenshot_width",
        "type": "int",
        "default": 384,
        "min": 96,
        "max": 1280,
        "label": "Ширина превью, px",
        "hint": "Снимок ужимается до этого размера ещё на хосте — по сети идёт уже маленький файл.",
    },
    "height": {
        "key": "screenshot_height",
        "type": "int",
        "default": 216,
        "min": 54,
        "max": 720,
        "label": "Высота превью, px",
        "hint": "Соотношение сторон — как договоритесь с шириной (по умолчанию 16:9).",
    },
    "jpeg_quality": {
        "key": "screenshot_jpeg_quality",
        "type": "int",
        "default": 72,
        "min": 10,
        "max": 95,
        "label": "Качество JPEG",
        "hint": "Выше — чётче картинка и больше файл. 70-80 обычно достаточно для превью.",
    },
}


class ScreenshotSettings:
    """Чтение и запись настройки снимков рабочего стола в `app_settings`."""

    def __init__(self, db):
        self.db = db

    # --- чтение ------------------------------------------------------------

    def get_config(self) -> dict:
        """Текущая настройка. Битое или отсутствующее значение молча заменяется
        значением по умолчанию: настройка превью не должна ронять фоновый цикл."""
        store = self.db.app_settings
        config: dict = {}
        for name, spec in FIELDS.items():
            config[name] = self._coerce(name, store.get(spec["key"]))
        return config

    def schema(self) -> dict:
        """Описание полей для страницы «Администрирование»."""
        return FIELDS

    # --- запись ------------------------------------------------------------

    def set_config(self, **values) -> dict:
        """Записывает переданные поля (остальные не трогает) и отдаёт итог."""
        store = self.db.app_settings
        for name, raw in values.items():
            spec = FIELDS.get(name)
            if spec is None or raw is None:
                continue
            store.set(spec["key"], str(self._coerce(name, raw)))
        return self.get_config()

    # --- приведение значений ----------------------------------------------

    @staticmethod
    def _coerce(name: str, raw):
        spec = FIELDS[name]
        if raw is None:
            return spec["default"]

        if spec["type"] == "bool":
            if isinstance(raw, bool):
                return raw
            return str(raw).strip().lower() in ("1", "true", "yes", "on")

        try:
            value = int(float(str(raw).strip()))
        except (TypeError, ValueError):
            return spec["default"]
        return max(spec["min"], min(spec["max"], value))
