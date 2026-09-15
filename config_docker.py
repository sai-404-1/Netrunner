"""Docker-specific NetRunner configuration template.

All values are loaded from environment variables. No credentials or
passphrases are hardcoded here. In a Docker build this file is typically
copied to config.py.
"""

import os

KEY_NAME = os.environ.get("NETRUNNER_KEY_NAME", "id_ed25519")
KEY_PATH = os.environ.get("NETRUNNER_KEY_PATH", "/app/keys")

SSH_STRICT_HOST_KEY_CHECKING = os.environ.get(
    "NETRUNNER_SSH_STRICT_HOST_KEY_CHECKING", "yes"
)
SSH_KNOWN_HOSTS_FILE = os.environ.get(
    "NETRUNNER_SSH_KNOWN_HOSTS_FILE", "/app/keys/known_hosts"
)
SSH_CHECK_HOST_IP = os.environ.get("NETRUNNER_SSH_CHECK_HOST_IP")

# Каталог для загруженных файлов (том netrunner_uploads).
UPLOADS_PATH = os.environ.get("NETRUNNER_UPLOADS_PATH", "/app/uploads")

# Каталог для скриншотов рабочих столов (том netrunner_data или рядом с БД).
SCREENSHOTS_PATH = os.environ.get("NETRUNNER_SCREENSHOTS_PATH", "/app/data/screenshots")

# Максимум одновременных передач файлов на хосты за одну задачу (<=0 — без лимита).
MAX_PARALLEL_TRANSFERS = int(os.environ.get("NETRUNNER_MAX_PARALLEL_TRANSFERS", "3"))

HOSTS = []
