# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

NetRunner is an SSH orchestration tool for managing fleets of Linux hosts. Operators add hosts, group them, and run "modules" (SSH command bundles) against a host or group — synchronously per-host with live status, cancellation, scheduling, and report export. It ships as a Python `aiohttp` backend plus a Next.js frontend, packaged in a single Docker container.

**The codebase is bilingual: most comments, docstrings, log messages, and all UI text are in Russian.** Match the surrounding language when editing — keep Russian strings Russian.

## Per-directory documentation (READMEs)

Almost every source directory contains a `README.md` (in Russian) that documents what
each file in that directory is responsible for and the key functions/classes it exposes.
**Consult the directory's `README.md` first** when you need to understand or change code
there — it's the fastest map of the codebase. Current coverage: `computer/`,
`computer/module/`, `computer/users_module/`, `database/`, `database/models/`,
`database/repos/`, `services/`, `webui/`, `modules/`, `frontend/`, `frontend/app/`,
`frontend/components/`, `frontend/lib/`. When you add or significantly change files in a
documented directory, update that directory's `README.md` to match.

## Commands

### Local development (no Docker)
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 web_main.py --host 127.0.0.1 --port 8000   # backend; SQLite at data/netrunner.db
cd frontend && npm install && npm run dev            # frontend dev server on :3000
```
The backend serves a legacy static UI at `/` (from `webui/static/`); the Next.js app in `frontend/` is the real frontend and proxies to the backend via `/api/python/*`.

### Docker (full stack)
```bash
./setup.sh            # == docker compose up --build -d
docker compose down   # stop;  add -v to also wipe data volumes
```
Container exposes Next.js on **port 3001** (compose maps `3001:3000`); the Python backend runs internally on `127.0.0.1:8000` and is not exposed.

### Tests
There is no pytest setup. Tests are standalone scripts run directly:
```bash
python3 tests_async_cancel.py     # custom harness: concurrent run, cancel, async SSH cancel
python3 test_apt_module.py        # unittest.TestCase + an asyncio mocked run
# single unittest case:
python3 -m unittest test_apt_module.TestAptPackageManager.test_build_command_install
```
`tests_async_cancel.py` injects a fake `config` module before importing project code — follow that pattern when a test needs to import code that does `from config import *`.

### Frontend lint
```bash
cd frontend && npm run lint
```

## Architecture

### Single entry point, two servers
In production all browser traffic hits the **Next.js frontend**, which proxies API calls to the **Python backend** under `/api/python/*` (the rewrite in `frontend/next.config.js` strips that prefix). So a browser call to `/api/python/api/hosts` reaches the backend as `/api/hosts`. Next.js requires `output: "standalone"` for the container to run `node server.js`. WebSocket `/ws` is not proxied by the Next rewrite.

### AppContext is the wiring hub
`services/app_context.py::create_app_context()` builds one `AppContext` that holds the DB, all services, the module registry, the task runner, the scheduler, auth, and reports. Both `web_main.py` and any CLI entry use it. On startup it: opens the DB (creating/migrating schema), registers built-in + user modules, loads disk modules, seeds task templates, creates the default `admin/admin` user, and runs one scheduler tick.

### The module system (the main extension point)
A "module" is a Python class run against hosts. Modules come from three sources, all funneled through `ModuleRegistry` (`services/module_registry.py`), which mirrors each runtime instance into the `modules` DB table (slug, schema JSON, builtin flag, enabled flag):

1. **Built-in** — `computer/module/`, collected by `computer.module.Modules` (see its `__init__.py` imports).
2. **Bundled user modules** — `computer/users_module/`, collected by `UserModules`.
3. **Disk-uploaded modules** — `.py` files dropped in `modules/` (local) or `/app/modules` (Docker, the `netrunner_modules` volume). They must export a class named `UserModule`. Uploads via the API write to `/app/modules` (`_install_uploaded_module` in `webui/server.py`); the disk loader (`_load_user_modules_from_disk`) reads `/app/modules` then falls back to `modules/`.

A module implements **one of two execution interfaces** (detected via `hasattr`):
- `async run_for_host(self, context, host, **kwargs) -> dict` — **preferred**; the runner calls it concurrently per host. Return a dict with host metadata + `output` (and optional `status`, `inventory_item`).
- `run(self, context, targets, **kwargs)` — sync fallback, executed in a thread; return a dict with `summary_text` / `per_host_results`, a str, or any JSON-able value.

For simple "run this SSH command with `$variable` substitution" modules, subclass `CommandModule` (`computer/module/base_module.py`) and just set `slug`, `title`, `description`, `command`, `schema` — it provides `run_for_host` and `shlex.quote`s substituted values. **Do not** route the four custom-parsing modules through `CommandModule`: `availability_check`, `inventory_collect`, `mass_ssh`, `apt_package_manager` each have bespoke `run_for_host`/`run` logic (see `.internal/TECHDEBT.md`). Schema field types currently supported: `text`, `textarea`, `password`, `select`.

### Task execution & lifecycle
`services/task_runner.py::TaskRunner` is async-first. `POST /api/run` creates a `pending` task_run row, returns immediately with `{run_id}`, and runs the work as a tracked background asyncio task; clients poll `GET /api/run/{id}/status` or subscribe over `/ws` (the server broadcasts on each update). The runner resolves the target (`host` or `group` via `HostService.resolve_targets`), runs per-host concurrently with `asyncio.gather`, stores results in `per_host_json`, and transitions status `pending → running → success | error | cancelled`. `cancel(run_id)` cancels the tracked task (which cancels in-flight per-host SSH subprocesses, since they're child tasks). A host result counts as an error if `status == "error"` or `output` starts with `[ERROR]`.

### SSH layer
All remote execution shells out to the system `ssh`/`scp` (no paramiko). `computer/module/executor_ssh.py` builds commands with list-style args, wraps the remote command in `sh -lc {shlex.quote(...)}`, and enforces host-key checking. `_ssh_common_options()` reads policy from `config.py` (`StrictHostKeyChecking`, known-hosts file, etc.). `computer.Computer` is the thin facade modules use (`async_executor_ssh`, etc.); `HostService.to_computer(host)` builds one with the host's SSH key path. Key generation/provisioning (`ssh-copy-id` via `sshpass`, with the password passed through `SSHPASS` env) lives in `webui/server.py`.

### Database layer (hand-rolled, no ORM library)
`database/orm.py::Database` opens the SQLite connection, runs `create_schema`, and exposes one repo per table as attributes (`db.hosts`, `db.modules`, `db.task_runs`, `db.users`, `db.boards`, ...). Repos live in `database/repos/` (extend `base.py`); row models are dataclasses in `database/models/`. `database/schema.py` holds the full `CREATE TABLE` SQL **and** idempotent migrations via `_add_column_if_missing` — when adding a column to an existing table, add it both to the `CREATE TABLE` and to a migration helper so existing DBs upgrade in place. `web_main.py` and the periodic ping daemon open their own short-lived `Database` connections rather than sharing one across threads.

### Auth
Token-based, in `services/auth_service.py` + `webui/auth_middleware.py`. Passwords are PBKDF2-SHA256. On login the token is stored on the user row and accepted three ways: `Authorization: Bearer <t>`, `?token=`, or the `netrunner_token` cookie. `auth_middleware` protects everything under `/api/*` except login/register. Note there is a built-in **service/superuser account** (`_SVC_U`/`_SVC_P`, base64-obfuscated in `auth_service.py`) whose token is regenerated each process start and never stored in the DB. First-run seeds `admin/admin`.

On the frontend, `frontend/middleware.ts` redirects unauthenticated requests to `/login`. Server-side data fetching (`frontend/lib/api.ts`, `"use server"`) calls the backend directly with the Bearer token read from the cookie; client components call `/api/python/*` with `credentials: "include"` so the cookie rides along. The login route (`frontend/app/api/login/route.ts`) sets the httpOnly cookie.

### Config
`config.py` (env-driven, secure defaults) is the live config; `executor_ssh.py` does `from config import *`. In Docker the build copies `config_docker.py` → `config.py`. Security-relevant settings (`NETRUNNER_SSH_STRICT_HOST_KEY_CHECKING`, key name/path, known-hosts file, check-host-IP) are all environment overrides — see the table in `README.md`.

## Reference docs in repo
- `README.md` — deployment, API endpoint list, env vars, test-host setup.
- Per-directory `README.md` files document each directory's files and functions (see the section above).

### Internal dev docs (`.internal/`, gitignored — local only, not published)
- `.internal/TECHDEBT.md` — which modules can't use `CommandModule` and why; schema field-type roadmap.
- `.internal/REVIEW.md`, `.internal/SSH_SECURITY_FIXES.md`, `.internal/CHANGELOG.md` — original code review, SSH hardening details, change history.
