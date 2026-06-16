# NetRunner — change log

This document summarizes the changes made to the NetRunner project during the improvement pass.

## 0. Accounts and authentication foundation

- Added `users` table (`database/schema.py`) with `username`, `email`, `password_hash`, `token`, `is_active`, `is_superuser`, `created_at`, `updated_at`.
- Added `User` model (`database/models/user.py`) and `UserRepo` (`database/repos/user_repo.py`).
- Added `AuthService` (`services/auth_service.py`) with password hashing (PBKDF2-SHA256), login token generation, and a default `admin`/`admin` user created on first start.
- Added protected API endpoints in `webui/server.py`:
  - `POST /api/login` — returns a bearer token and user info.
  - `POST /api/register` — creates a new user.
  - `POST /api/logout` — invalidates the token.
  - `GET /api/me` — returns the current user.
- Added `webui/auth_middleware.py` and `webui/auth_handlers.py`; all API routes except login/register require a valid `Authorization: Bearer <token>` header.
- `AppContext` now exposes `auth_service` and creates the default user on bootstrap.

## 1. Next.js frontend integration and single-container deployment

- Added a multi-stage `Dockerfile` that:
  - Builds the Next.js frontend from `frontend/` when it exists.
  - Installs Node.js and npm into the Python 3.11 Alpine image so the Next.js standalone server can run.
  - Copies the built standalone output to `/app/frontend` in the final image.
- Updated `docker-compose.yml` to expose only port `3000:3000`. The Python backend is no longer exposed directly.
- Rewrote `startup.sh` to:
  - Initialize the database and SSH key as before.
  - Start the Python backend on `127.0.0.1:8000` (internal only).
  - Wait for the backend to become ready, then start the Next.js standalone server on port 3000.
  - Gracefully shut down both services on SIGTERM/SIGINT.
- Updated `setup.sh` to report the new web interface URL: `http://localhost:3000`.
- Updated `.dockerignore` to exclude `frontend/node_modules`, `frontend/.next`, `frontend/out`, and `frontend/dist`.
- Added `README.md` documentation for the new frontend-first architecture, including the required Next.js rewrite configuration (`output: 'standalone'` and `/api/python/:path* -> http://127.0.0.1:8000/:path*`).
- Documented the WebSocket caveat: Next.js rewrites handle HTTP, so `/ws` must be proxied separately if the new frontend uses it.

## 2. Asynchronous web server

- Replaced the single-threaded `http.server` implementation in `webui/server.py` with an `aiohttp`-based async server.
- All HTTP handlers are now coroutines, so long-running operations (host checks, task runs, scheduler ticks) do not block the event loop.
- Added `POST /api/run` which starts a task in the background and returns `{run_id, status}` immediately.
- Added `GET /api/run/<id>/status` for polling status and per-host results.
- Added WebSocket endpoint `WS /ws` that pushes live task status updates to connected clients.
- Background tasks are tracked in `app["background_tasks"]` and cancelled gracefully on shutdown.
- Updated `requirements.txt` to include `aiohttp>=3.8.0` and `cryptography>=41.0.0`.
- Updated `Dockerfile` and `startup.sh` to start the new async server.

## 3. Asynchronous per-host task execution

- Rewrote `services/task_runner.py` with `asyncio`:
  - `run_async()` executes modules concurrently for each target host.
  - `_run_per_host()` creates one `asyncio.Task` per host and logs results as they arrive.
  - `_run_one_host()` supports both async and sync `run_for_host` methods, running the latter in `asyncio.to_thread`.
  - `cancel()` cancels every tracked running task.
  - `TaskRun` rows are updated with `status=running`, `success`, `error`, or `cancelled` and a `per_host_json` field.
- Added async variants to `services/host_service.py`: `check_host_async()` and `check_all_hosts_async()` run host checks through `asyncio` subprocesses.
- Added `services/scheduler.py` `tick_async()` to fire scheduled tasks in the background without blocking the HTTP event loop.
- Added `tests_async_cancel.py` demonstrating concurrent execution and cancellation.

## 4. SSH key generation through the Web UI

- Added `POST /api/keys/generate` in `webui/server.py`.
- Supports RSA (`2048` bits) and ED25519 key types, with optional passphrase protection.
- Uses the `cryptography` library to generate keys and OpenSSH-style fingerprints.
- Stores private keys only on disk with `0o600` permissions; public keys are stored with `0o644`.
- Persists metadata (`name`, `key_type`, `public_key`, `fingerprint`, `has_passphrase`) in the SQLite database, but never the plaintext private key.
- Schema migration in `database/schema.py` adds `key_type`, `public_key`, `private_key`, and `fingerprint` columns to `ssh_keys` if they are missing.
- Provisioning via `ssh-copy-id` uses `SSHPASS` environment variable instead of a command-line password.

## 5. SSH security hardening

- `computer/module/executor_ssh.py` now uses strict host-key verification by default:
  - `StrictHostKeyChecking=yes`
  - `BatchMode=yes`
  - `ConnectTimeout=5`
  - Optional `UserKnownHostsFile` and `CheckHostIP` via `config.py`.
- Added `async_main()` in `executor_ssh.py` that runs the SSH subprocess via `asyncio.create_subprocess_exec` and kills the process on cancellation.
- `computer/module/executor_scp.py`, `hard_drive_check.py`, `folder_swipe.py`, and `installer.py` now reuse `_ssh_common_options()` from `executor_ssh.py` and pass commands as list arguments instead of shell strings.
- `folder_swipe.py` and `installer.py` quote user-provided paths/package names with `shlex.quote` to prevent command injection.
- `config.py` and `config_docker.py` load all deployment values from environment variables; no credentials are hardcoded.
- Removed any hardcoded private keys from the code path. The default key is generated on first container start by `startup.sh`.
- Details are documented in `SSH_SECURITY_FIXES.md`.

## 6. Web UI front-end improvements

- Added a WebSocket client in `webui/static/app.js` that connects to `WS /ws` and receives live task status updates.
- The task run page now polls `/api/run/{id}/status` and also subscribes to WebSocket updates for the active run.
- Added a **Cancel** button on the run page that calls `POST /api/run/{id}/cancel` and stops a running/pending task.
- Added per-host result rendering on both the run page and the history table.
- Added `cancelled` status to the task status badge/label mapping.
- Added `.warning` badge style and `.per-host-result` CSS classes in `styles.css`.
- Added a new `POST /api/run/{id}/cancel` endpoint in `webui/server.py`.
- Updated `TaskRunner` to track `task_run_id -> asyncio.Task` mappings so individual task runs can be cancelled.

## 7. Configuration and environment

- Created a new `config.py` (and `config_docker.py` for Docker) with environment-variable based defaults.
- Updated `.dockerignore` to keep the build context small.
- Updated `README.md` with the new architecture, API endpoints, configuration table, and quick-start instructions.
- Created this `CHANGELOG.md`.

## 8. Bug fixes found during review

- `services/module_registry.py` only considered modules with a `run` method as schedulable, so modules that implement only `run_for_host` were rejected by the runner. Now `supports_task_runner` is true when either method exists.
- `computer/module/folder_swipe.py` was checking `result.stderr == 0` instead of `result.returncode == 0` to decide success/failure.
- `computer/module/hard_drive_check.py` returned the raw `subprocess.run` object instead of the command output; now it captures stdout/stderr and returns the formatted output.
- `webui/server.py` had an orphaned `@staticmethod` decorator on a module-level function; removed it.
- `services/scheduler.py` was missing an `import asyncio` for `tick_async()`; added it.
- `webui/static/index.html` referenced `/styles.css` and `/app.js` but the server serves static files under `/static/`, so styles and scripts were not loaded in Docker. Fixed to `/static/styles.css` and `/static/app.js`.

## 9. APT package manager module

- Added `computer/module/apt_package_manager.py` with a built-in module that supports:
  - `install`, `remove`, `update`, `autoremove` actions via `apt-get` over SSH.
  - Per-host concurrent execution through `run_for_host`.
  - Context logging for every action (`task_run`, host, action, packages, changed, failed, status).
  - Structured per-host results with `action`, `packages`, `changed`, `failed`, `returncode`, `stdout`, `stderr`.
  - Optional sudo password passed via stdin for `sudo -S`.
- Registered the module in `computer/module/__init__.py` so it appears as a built-in module in the web UI.
- Added a default task template in `services/app_context.py` for `apt_package_manager`.
- Added web UI controls in `webui/static/index.html` and `webui/static/app.js` for selecting action, entering packages, and providing an optional sudo password.

## Known limitations

- The new Next.js frontend must be configured with `output: 'standalone'` and the `/api/python/:path* -> http://127.0.0.1:8000/:path*` rewrite for the single-entry-point proxy to work. WebSocket traffic (`/ws`) is not handled by Next.js HTTP rewrites, so it must be proxied separately if the frontend uses it.
- Host-key verification is strict by default. In a fresh Docker demo the test hosts share the same volume, so keys can be added automatically with `ssh-copy-id` when the host password is provided; otherwise the operator must accept host keys manually.
- The async server uses a single process. For very large numbers of concurrent SSH connections the operator may want to run behind a reverse proxy or increase file descriptor limits.
