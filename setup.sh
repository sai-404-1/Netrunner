#!/usr/bin/env bash
# NetRunner deployment setup
# Builds and starts the NetRunner web server + Alpine test hosts.

set -e

echo "[NetRunner] Starting deployment setup..."

# Check that Docker is available
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed or not in PATH." >&2
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "ERROR: Docker Compose is not available." >&2
    exit 1
fi

# Build and start all services
if docker compose version &> /dev/null; then
    docker compose up --build -d
else
    docker-compose up --build -d
fi

echo "[NetRunner] Services are starting up."
echo "[NetRunner] Web interface: http://localhost:3000"
echo "[NetRunner] Test hosts:    host-1:2221, host-2:2222, host-3:2223"
echo "[NetRunner] To view logs:  docker compose logs -f netrunner"
echo "[NetRunner] To stop:       docker compose down"
