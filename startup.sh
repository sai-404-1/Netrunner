#!/bin/sh
# NetRunner startup script for Docker
# Initializes the database and SSH key, then starts the Python backend and
# the Next.js standalone frontend on port 3000.

set -e

APP_DIR="/app"
DB_PATH="${APP_DIR}/data/netrunner.db"
FRONTEND_DIR="${APP_DIR}/frontend"
FRONTEND_PORT=3000
PYTHON_HOST="127.0.0.1"
PYTHON_PORT=8000

# Ensure directories exist
mkdir -p "${APP_DIR}/data" "${APP_DIR}/keys" "${APP_DIR}/reports" "${APP_DIR}/modules"

# Generate SSH key if it doesn't exist
if [ ! -f "${APP_DIR}/keys/id_ed25519" ]; then
    echo "[startup] Generating SSH key..."
    ssh-keygen -t ed25519 -f "${APP_DIR}/keys/id_ed25519" -N "" -C "netrunner@docker"
    echo "[startup] SSH key generated. Public key:"
    cat "${APP_DIR}/keys/id_ed25519.pub"
fi

# Initialize database with demo data if it doesn't exist
if [ ! -f "${DB_PATH}" ]; then
    echo "[startup] Database not found. Creating with demo data..."
    cd "${APP_DIR}"
    python init_demo.py --docker
else
    echo "[startup] Database found at ${DB_PATH}"
fi

# Hand off to the supervisor (PID 1): it runs the backend + frontend, does the
# health-check, distinguishes update-restarts from crashes, and performs phoenix
# recovery (code rollback + DB restore) on a crash loop. See supervise.py / CLAUDE.md.
echo "[startup] Передаю управление супервизору (supervise.py)..."
exec python3 "${APP_DIR}/supervise.py"
