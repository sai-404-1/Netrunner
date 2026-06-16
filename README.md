# NetRunner — deployment package

This folder contains everything needed to build and run NetRunner with three Alpine test hosts on any machine that has Docker.

NetRunner now serves both the new **Next.js frontend** and the existing **Python aiohttp backend** from a single container. The frontend listens on port **3000** and proxies requests to the Python backend internally on port **8000**. The backend is no longer exposed directly.

## Quick start

```bash
cd /home/justsai/Downloads/netrunner_extracted
./setup.sh
```

Then open the web interface at **http://localhost:3000**.

To stop everything:

```bash
docker compose down
```

To stop and remove all data volumes as well:

```bash
docker compose down -v
```

## What is included

- `Dockerfile` — multi-stage build: builds the Next.js frontend (if present), then creates a Python 3.11 + Alpine image that runs both services.
- `docker-compose.yml` — starts NetRunner and three test SSH hosts.
- `startup.sh` — runs inside the container to generate an SSH key, initialize the database, start the Python backend on `127.0.0.1:8000`, and start the Next.js frontend on port 3000.
- `host_startup.sh` — runs inside each Alpine host to create a user and install the public key from NetRunner.
- `requirements.txt`, `config_docker.py`, `init_demo.py`, `web_main.py` — application code and dependencies.
- `computer/`, `database/`, `services/`, `webui/` — NetRunner source directories.
- `modules/` — empty folder. User-uploaded modules are persisted here via the `netrunner_modules` volume.
- `.dockerignore` — keeps the build context small.
- `setup.sh` — convenience script that runs `docker compose up --build -d`.
- `frontend/` — Next.js frontend (created by another agent). When it is present, the container builds it as a standalone server and runs it alongside the Python backend.

## Single entry point

Only port **3000** is exposed by the container. The frontend is the single entry point for all traffic:

- All browser requests go to **http://localhost:3000**.
- The frontend proxies API calls to the Python backend under the path `/api/python/*`.
- The Python backend runs on `127.0.0.1:8000` inside the container and is not reachable from outside directly.

### Frontend configuration required

For the proxy to work, `frontend/next.config.js` (or `.mjs`/`.ts`) must include these two settings:

1. `output: 'standalone'` so the container can run `node server.js`.
2. A rewrite that strips `/api/python` and forwards the rest to the Python backend:

```js
const nextConfig = {
  output: 'standalone',
  async rewrites() {
    return [
      {
        source: '/api/python/:path*',
        destination: 'http://127.0.0.1:8000/:path*',
      },
    ];
  },
};

module.exports = nextConfig;
```

With this rewrite, a frontend request to `/api/python/api/hosts` reaches the backend as `/api/hosts`.

> **Note:** Next.js rewrites handle HTTP requests. If the new frontend uses the WebSocket endpoint `/ws`, it must be proxied separately (for example, by connecting the browser through an API route or by using a dedicated reverse proxy). The backend exposes `/ws` on `127.0.0.1:8000` inside the container.

## Test SSH hosts

The Compose file creates three Alpine hosts for demonstration:

| Host     | Container name      | Address from NetRunner | Port on host machine |
|----------|---------------------|------------------------|----------------------|
| host-1   | netrunner-host-1    | host-1:22              | 2221                 |
| host-2   | netrunner-host-2    | host-2:22              | 2222                 |
| host-3   | netrunner-host-3    | host-3:22              | 2223                 |

NetRunner automatically generates an ED25519 SSH key on first start and makes the public key available to the test hosts via a shared volume. The hosts can be added in the NetRunner web UI as:

- **username:** `admin`
- **address:** `host-1` (or `host-2`, `host-3`)
- **port:** `22`
- **SSH key:** `id_ed25519` (default key created by NetRunner)

The default password for the test users is `admin`.

## Persistent data

The following Docker volumes keep data across restarts:

- `netrunner_data` — SQLite database (`/app/data`).
- `netrunner_keys` — SSH keys (`/app/keys`).
- `netrunner_reports` — generated reports (`/app/reports`).
- `netrunner_modules` — user-uploaded modules (`/app/modules`).

## Windows/macOS/Linux

Because the application runs inside Docker, the same commands work on Windows, macOS, and Linux. On Windows, use PowerShell, WSL, or any terminal that has Docker installed.

## Recent improvements

- **Next.js frontend integration** — the container now builds and runs a Next.js frontend as the single entry point. Port 3000 is the only exposed port; the Python backend is proxied internally on `127.0.0.1:8000`.
- **Asynchronous web server** — the web UI is served by an `aiohttp`-based server instead of the previous single-threaded `http.server`. Long-running SSH operations are dispatched as background `asyncio` tasks, so the HTTP API stays responsive and can be polled for status.
- **Asynchronous task execution** — tasks run concurrently per host. Each host is handled in its own `asyncio` task, results are logged as soon as they arrive, and a task can be cancelled.
- **SSH key generation in the Web UI** — generate RSA or ED25519 key pairs directly from the browser. Passphrase-protected keys are supported. Private key material is stored only on disk (with `0o600` permissions); the API never returns it.
- **SSH security hardening** — host-key verification is enabled by default (`StrictHostKeyChecking=yes`), remote commands are built with list-style arguments and `shlex.quote`, and credentials are no longer hardcoded.
- **APT package manager module** — install, remove, update or autoremove Debian/Ubuntu packages across hosts. The module logs each action, records which packages were changed or failed per host, and supports an optional sudo password.

## API highlights

- `GET /api/hosts` — list hosts.
- `POST /api/run` — start a task. Returns immediately with `{run_id, status}`; execution happens in the background.
- `GET /api/run/<id>/status` — poll task status and per-host results.
- `POST /api/run/<id>/cancel` — cancel a running or pending task.
- `GET /api/ssh-keys` — list stored SSH keys (private key excluded).
- `POST /api/keys/generate` — generate a new SSH key pair (`rsa` or `ed25519`).
- `WS /ws` — receive live task status updates.

When calling the backend through the frontend, prefix these paths with `/api/python`, for example `GET /api/python/api/hosts`.

## Web UI highlights

- The task run page shows a live progress indicator, per-host results, and a **Cancel** button for active tasks.
- History table displays per-host summaries and supports viewing full per-host output in the modal.
- SSH key generation form creates RSA/ED25519 keys directly in the browser and shows the public key + fingerprint.
- WebSocket updates refresh the dashboard and history automatically as task statuses change.

## Configuration

NetRunner reads deployment settings from `config.py`. In Docker the build copies `config_docker.py` to `config.py`. All security-relevant values can be overridden through environment variables:

| Variable | Default | Meaning |
|----------|---------|---------|
| `NETRUNNER_KEY_NAME` | `id_ed25519` | SSH private key filename. |
| `NETRUNNER_KEY_PATH` | `/app/keys` in Docker, `keys` locally | Directory that holds SSH keys. |
| `NETRUNNER_SSH_STRICT_HOST_KEY_CHECKING` | `yes` | OpenSSH `StrictHostKeyChecking` value. Use `accept-new` only to trust new hosts on first use. |
| `NETRUNNER_SSH_KNOWN_HOSTS_FILE` | `/app/keys/known_hosts` in Docker | Explicit `UserKnownHostsFile`. |
| `NETRUNNER_SSH_CHECK_HOST_IP` | *(unset)* | Set to `no` when hosts are behind NAT. |

## Files worth reading

- `REVIEW.md` — original code review with findings and recommendations.
- `SSH_SECURITY_FIXES.md` — summary of SSH security fixes.
- `CHANGELOG.md` — list of changes made during this improvement pass.
- `tests_async_cancel.py` — example of concurrent task execution and cancellation.

## Running outside Docker (local development)

```bash
cd /home/justsai/Downloads/netrunner_extracted
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 web_main.py --host 127.0.0.1 --port 8000
```

The local SQLite database will be created at `data/netrunner.db` and SSH keys at `keys/`. The first start also imports `hosts.json` if it exists and creates the default key if needed.
