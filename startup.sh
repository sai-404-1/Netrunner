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

# Start Python backend bound to localhost only (internal to the container)
echo "[startup] Starting NetRunner Python backend on ${PYTHON_HOST}:${PYTHON_PORT}..."
python -m web_main --host "${PYTHON_HOST}" --port "${PYTHON_PORT}" &
PYTHON_PID=$!

# Wait for the Python backend to accept connections
READY=0
for i in $(seq 1 30); do
    if python -c "import socket; s=socket.socket(); s.settimeout(1); s.connect(('${PYTHON_HOST}', ${PYTHON_PORT})); s.close()" 2>/dev/null; then
        READY=1
        echo "[startup] Python backend is ready"
        break
    fi
    if ! kill -0 "${PYTHON_PID}" 2>/dev/null; then
        echo "[startup] Python backend exited unexpectedly"
        exit 1
    fi
    sleep 1
done

if [ "${READY}" -eq 0 ]; then
    echo "[startup] Python backend failed to become ready, stopping"
    kill "${PYTHON_PID}" 2>/dev/null || true
    wait "${PYTHON_PID}" 2>/dev/null || true
    exit 1
fi

# Start the Next.js standalone frontend if it was built
if [ -f "${FRONTEND_DIR}/server.js" ]; then
    echo "[startup] Starting Next.js frontend on port ${FRONTEND_PORT}..."
    cd "${FRONTEND_DIR}"
    PORT="${FRONTEND_PORT}" node server.js &
    FRONTEND_PID=$!
else
    echo "[startup] Next.js frontend not built yet; only the Python backend is running"
    FRONTEND_PID=""
fi

# Graceful shutdown: stop both services on SIGTERM/SIGINT
shutdown() {
    echo "[startup] Received shutdown signal, stopping services..."
    if [ -n "${FRONTEND_PID}" ]; then
        kill "${FRONTEND_PID}" 2>/dev/null || true
    fi
    kill "${PYTHON_PID}" 2>/dev/null || true
    wait 2>/dev/null || true
    exit 0
}

trap shutdown TERM INT

# Keep running until either service exits
while true; do
    if ! kill -0 "${PYTHON_PID}" 2>/dev/null; then
        echo "[startup] Python backend stopped"
        break
    fi
    if [ -n "${FRONTEND_PID}" ] && ! kill -0 "${FRONTEND_PID}" 2>/dev/null; then
        echo "[startup] Next.js frontend stopped"
        break
    fi
    sleep 1
done

shutdown
