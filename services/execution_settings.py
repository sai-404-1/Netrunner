"""Темп выполнения: пакетами по N машин или скользящим параллелизмом.

Зачем: на группе в полсотни компьютеров запуск «сразу на всех» кладёт и сеть, и
сервер, и сам класс. Пакетный режим пускает машины партиями — первые N прошли
свою очередь целиком, только потом стартует следующая партия.

Настройка живёт в `app_settings` и перечитывается **перед каждым запуском**, так
что правка со страницы «Администрирование» применяется к следующему запуску без
перезапуска сервера. Ключи, значения по умолчанию и границы описаны здесь одним
местом (`FIELDS`) — интерфейсу достаточно `get_config` / `set_config` / `schema`,
знать про имена ключей и валидацию ему не нужно.
"""

from __future__ import annotations

MODE_PARALLEL = "parallel"
MODE_BATCH = "batch"

# Пользователь, от чьего имени исполняются SSH-команды на целевых машинах:
#   service — сервисный netrunner-svc (его per-host ключ, root через sudo) — дефолт;
#   primary — первичный пользователь хоста (host.username + его ключ), тот же, под
#             которым хост добавлялся. Переключение глобальное и живёт на сервере —
#             на самих хостах ничего не меняется.
SSH_USER_SERVICE = "service"
SSH_USER_PRIMARY = "primary"

# Единственный источник правды по настройке: ключ в app_settings, значение по
# умолчанию, границы и подпись для интерфейса.
FIELDS: dict[str, dict] = {
    "ssh_user_mode": {
        "key": "execution_ssh_user_mode",
        "type": "choice",
        "default": SSH_USER_SERVICE,
        "choices": [
            {"value": SSH_USER_SERVICE, "label": "Сервисный (netrunner-svc)"},
            {"value": SSH_USER_PRIMARY, "label": "Первичный пользователь хоста"},
        ],
        "label": "Пользователь исполнения команд",
        "hint": (
            "От чьего имени NetRunner выполняет команды на целевых машинах. "
            "Сервисный — netrunner-svc (root через sudo, ключ агента). "
            "Первичный — пользователь, под которым хост добавлен. "
            "Переключение глобальное, на хостах ничего не меняется."
        ),
    },
    "mode": {
        "key": "execution_mode",
        "type": "choice",
        "default": MODE_PARALLEL,
        "choices": [
            {"value": MODE_PARALLEL, "label": "Все машины сразу (до лимита)"},
            {"value": MODE_BATCH, "label": "Пакетами по N машин"},
        ],
        "label": "Режим выполнения",
        "hint": "Пакетный режим ждёт, пока партия машин пройдёт очередь целиком, и только потом берёт следующую.",
    },
    "batch_size": {
        "key": "execution_batch_size",
        "type": "int",
        "default": 5,
        "min": 1,
        "max": 500,
        "label": "Машин в пакете",
        "hint": "Сколько компьютеров работает одновременно в пакетном режиме.",
    },
    "batch_delay": {
        "key": "execution_batch_delay",
        "type": "int",
        "default": 0,
        "min": 0,
        "max": 3600,
        "label": "Пауза между пакетами, с",
        "hint": "Даёт сети и серверу выдохнуть между партиями. 0 — без паузы.",
    },
    "max_parallel": {
        "key": "execution_max_parallel",
        "type": "int",
        "default": 10,
        "min": 1,
        "max": 500,
        "label": "Одновременно машин",
        "hint": "Потолок параллелизма, когда пакетный режим выключен.",
    },
    "agent_ws_url": {
        "key": "agent_ws_url",
        "type": "ws_url",
        "default": "",
        "label": "Адрес сервера для агента",
        "hint": (
            "WebSocket-адрес, который endpoint-агент на хостах использует для "
            "связи с сервером, например ws://180.161.0.3:3001 — путь /api/python/"
            "agent/ws дописывается сам, если его не указать. Записывается в "
            "конфиг агента при установке/переустановке. Пусто — берётся из "
            "переменной окружения NETRUNNER_AGENT_WS_URL, а если и она не "
            "задана — определяется автоматически (в Docker так не работает). "
            "После смены адреса агента на хостах нужно переустановить."
        ),
    },
    "agent_ca_cert": {
        "key": "agent_ca_cert",
        "type": "pem_cert",
        "default": "",
        "label": "Корневой сертификат сервера (для wss://)",
        "hint": (
            "PEM корня, которым подписан HTTPS-сертификат сервера. При установке "
            "агента кладётся в /etc/netrunner-agent/ca.crt, и для wss:// агент "
            "доверяет только ему — системное хранилище машины не используется. "
            "Нужен, если адрес агента начинается с wss://. Только сертификат: "
            "закрытый ключ сюда не вставлять. После смены — переустановить агентов."
        ),
    },
    "coldawn_retries": {
        "key": "execution_coldawn_retries",
        "type": "int",
        "default": 3,
        "min": 0,
        "max": 20,
        "label": "Повторы запуска (coldawn)",
        "hint": (
            "Сколько раз повторить запуск сценария на машине, если он не смог "
            "даже начаться (ошибка соединения/старта первого шага). 0 — не "
            "повторять. По исчерпании попыток машина пропускается, очередь "
            "переходит к следующей."
        ),
    },
}


# Путь эндпоинта агента на сервере (server/endpoints/api_websocket.py регистрирует
# голый /agent/ws; наружу он торчит через прокси Next.js под префиксом /api/python/
# — см. frontend/next.config.js). Самая частая ошибка при ручном вводе адреса —
# вставить просто "хост:порт" без пути, поэтому недостающий путь дописывается сам.
_AGENT_WS_PATH = "/api/python/agent/ws"


def _is_ws_url(value: str) -> bool:
    """ws:// или wss:// с непустым хостом — остальное агент всё равно не откроет."""
    from urllib.parse import urlparse
    parsed = urlparse(value)
    return parsed.scheme in ("ws", "wss") and bool(parsed.netloc)


def _normalize_ws_url(value: str, default: str = "") -> str:
    """Обрезает пробелы/слэш и дописывает путь агента, если ввели голый хост:порт.

    Невалидное непустое значение откатывается к default — сюда долетают только
    значения, уже пропущенные валидацией set_config(), но get_config() читает
    то, что реально лежит в БД, и должен остаться устойчив к ручной правке.
    """
    from urllib.parse import urlparse
    value = value.strip().rstrip("/")
    if not value:
        return value
    if not _is_ws_url(value):
        return default
    parsed = urlparse(value)
    if not parsed.path:
        value = f"{value}{_AGENT_WS_PATH}"
    return value


def ca_cert_info(pem: str) -> dict:
    """Проверяет PEM корня для агента и отдаёт сводку для страницы настроек.

    ValueError с понятным текстом, если это не ровно один сертификат УЦ.
    """
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes

    text = (pem or "").strip()
    if "PRIVATE KEY" in text:
        raise ValueError("вставлен закрытый ключ — нужен только сертификат (BEGIN CERTIFICATE)")
    if text.count("-----BEGIN CERTIFICATE-----") != 1:
        raise ValueError("нужен ровно один сертификат в формате PEM (-----BEGIN CERTIFICATE-----)")
    try:
        cert = x509.load_pem_x509_certificate(text.encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        raise ValueError("не удалось разобрать сертификат")
    try:
        is_ca = cert.extensions.get_extension_for_class(x509.BasicConstraints).value.ca
    except x509.ExtensionNotFound:
        is_ca = False
    if not is_ca:
        raise ValueError("это не корневой сертификат (нет CA:TRUE) — нужен корень, которым подписан сертификат сервера")
    not_after = getattr(cert, "not_valid_after_utc", None) or cert.not_valid_after
    digest = cert.fingerprint(hashes.SHA256()).hex().upper()
    return {
        "subject": cert.subject.rfc4514_string(),
        "not_after": not_after.isoformat(),
        "sha256": ":".join(digest[i:i + 2] for i in range(0, len(digest), 2)),
    }


class ExecutionSettings:
    """Чтение и запись настроек темпа выполнения в `app_settings`."""

    def __init__(self, db):
        self.db = db

    # --- чтение ------------------------------------------------------------

    def get_config(self) -> dict:
        """Текущая настройка. Битое или отсутствующее значение молча заменяется
        значением по умолчанию: настройка темпа не должна ронять запуск."""
        store = self.db.app_settings
        config: dict = {}
        for name, spec in FIELDS.items():
            config[name] = self._coerce(name, store.get(spec["key"]))
        return config

    def schema(self) -> dict:
        """Описание полей для страницы «Администрирование» — подписи, границы,
        варианты выбора. Форму можно отрисовать, не зашивая их в интерфейс."""
        return FIELDS

    # --- запись ------------------------------------------------------------

    def set_config(self, **values) -> dict:
        """Записывает переданные поля (остальные не трогает) и отдаёт итог.

        Значения приводятся к границам, а не отвергаются: настройка темпа —
        не тот случай, где стоит отказывать пользователю из-за лишнего нуля.
        Неизвестные имена полей игнорируются.
        """
        store = self.db.app_settings
        for name, raw in values.items():
            spec = FIELDS.get(name)
            if spec is None or raw is None:
                continue
            # Адрес с опечаткой молча откатился бы к пустому — админ решил бы, что
            # сохранил, а агенты продолжили бы ходить по старому адресу.
            if spec["type"] == "ws_url":
                stripped = str(raw).strip().rstrip("/")
                if stripped and not _is_ws_url(stripped):
                    raise ValueError(
                        f"{spec['label']}: нужен адрес вида ws://хост:порт/путь или wss://…"
                    )
            if spec["type"] == "pem_cert" and str(raw).strip():
                try:
                    ca_cert_info(str(raw))
                except ValueError as exc:
                    raise ValueError(f"{spec['label']}: {exc}")
            store.set(spec["key"], str(self._coerce(name, raw)))
        return self.get_config()

    # --- приведение значений ----------------------------------------------

    @staticmethod
    def _coerce(name: str, raw):
        spec = FIELDS[name]
        if raw is None:
            return spec["default"]

        if spec["type"] == "choice":
            value = str(raw).strip()
            allowed = {c["value"] for c in spec["choices"]}
            return value if value in allowed else spec["default"]

        if spec["type"] == "ws_url":
            return _normalize_ws_url(str(raw), default=spec["default"])

        if spec["type"] == "pem_cert":
            return str(raw).strip()

        try:
            value = int(float(str(raw).strip()))
        except (TypeError, ValueError):
            return spec["default"]
        return max(spec["min"], min(spec["max"], value))
