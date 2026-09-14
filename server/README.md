# webui

Бэкенд-сервер NetRunner на `aiohttp`: REST API под `/api/*`, WebSocket `/ws`,
аутентификация, админ-функции и доски. В проде браузерный трафик идёт через Next.js,
который проксирует API на этот сервер под `/api/python/*`.

## Файлы

### `server.py` — основной сервер и API
Точка сборки приложения и большинство хендлеров.
- `_build_app(app_context)` — собирает `web.Application`, middleware и регистрирует все маршруты.
- `run_web_server(app_context, host, port, open_browser, ping_interval)` — запуск панели.
- Утилиты (`tools.py`): `model_to_dict` (сериализация dataclass'ов; **скрывает** `password_encrypted`),
  `_ok`/`_error`/`_json_response`, `_read_json`, `_ctx`, `_safe_int`, `_require_admin`.
- **Доступ по кабинетам (`tools.py`)** — общий расчёт для роли `teacher`:
  `is_teacher(user)`, `allowed_group_ids(db,user)` / `allowed_host_ids(db,user)`
  (возвращают `None` = без ограничений, для суперпользователя и роли `user` без выданных
  кабинетов), `host_visible(db,user,host_id)`. Преподаватель видит и трогает только
  хосты/кабинеты из `user_group_access`; **пусто → не видит ничего** (в отличие от роли
  `user`, где пусто = видно всё). Применяются per-endpoint (не middleware).
- Фоновые задачи и WebSocket: `_run_background`, `_broadcast_task_update`,
  `websocket_handler`, `_periodic_ping` (демон проверки хостов),
  `_scheduler_loop` (фоновый цикл планировщика: раз в **60 секунд** `ctx.scheduler.tick_async()`
  — запланированные задачи выполняются сами), `_update_monitor` (демон git-монитора
  самообновления — кэширует статус в `app["update_status"]`).
- `healthz_handler` — публичный `/healthz` (200) для health-check супервизора.
- **Загруженные файлы (только админ):** `api_uploads_list/create/download/delete` —
  хранилище файлов для модуля рассылки (`_require_admin`, `_uploads_dir`, `_upload_to_dict`).
- **Обновление кода (только админ, Phase 2/3):** `api_update_status`, `api_update_recheck`,
  `api_update_set_config`, `api_update_apply` (после ответа завершает процесс → супервизор
  пересобирает/перезапускает), `api_update_incidents` (читает `data/incidents/*` и хвост
  `supervisor.log`). Старые `api_update_check/diff/pull` (git в контейнере) ещё есть, но UI
  на них не ходит.
- **Telegram (привязка/верификация):** `api_me_telegram_status/link/unlink` (любой
  залогиненный — привязка своего аккаунта через `/start <code>`), `api_admin_telegram_get/set`
  (админ — токен бота). Фоновый поллер `_telegram_poller` обрабатывает `/start <code>`.
- **2FA-вход через Telegram:** `api_login` принимает `device_id`; если Telegram привязан и
  устройство не доверенное — возвращает `mfa_required` и шлёт одноразовый код в Telegram
  (`_send_login_code`, `_mask_telegram`). Второй шаг — `api_login_verify` (`/api/login/verify`,
  публичный) сверяет код и выдаёт токен. Доверенные устройства пользователя:
  `api_me_devices_list` (`GET /api/me/devices`), `api_me_devices_trust` (сменить срок,
  напр. «навсегда»), `api_me_devices_revoke`. Идентификатор устройства — httpOnly-cookie
  `netrunner_device` (ставит Next.js login-route).
- **Хосты:** `api_hosts`, `api_hosts_create`, `api_hosts_update`, `api_hosts_delete`,
  `api_hosts_check`, `api_hosts_check_all`,
  `api_hosts_reprovision` — заново копирует SSH-ключ на хост (при отвале/удалении ключа),
  используя сохранённый или переданный пароль.
  **Права teacher:** `api_hosts`/`_check_all` отдают только его кабинеты; create/delete/reprovision —
  только админ; update/check — только на своих хостах (`host_visible`).
- **Группы:** `api_groups`, `api_groups_create/update/delete/add_host`.
  **Права teacher:** `api_groups` отдаёт только его кабинеты; create/update/delete/add_host —
  только админ (`_deny_teacher`).
- **Модули:** `api_modules`, `api_modules_create/update/delete`.
- **Задачи:** `api_run` (старт в фоне, возврат `run_id`), `api_run_cancel`,
  `api_task_runs`, `api_task_run_status`, `api_task_runs_clear`.
  **Права teacher:** `api_run` проверяет, что все цели в его кабинетах; `api_task_runs` и
  `api_task_run_status` фильтруются по кабинетам (запуск виден, если участвовал хотя бы
  один его хост — по `per_host_json`/`target`).
- **Планировщик:** `api_scheduled`, `api_schedule_create/update/delete`, `api_scheduler_tick`
  (ручной тик). Логика в `domens/scheduled.py`; каждая задача привязана к **сценарию**
  (`scenario_id`), исполняет её `Scheduler` → `ScenarioRunner`. Create/update принимают
  recurring-расписание (дни недели, окно «С…До», интервал) с жёсткой валидацией.
- **Инвентаризация/сводка/отчёты:** `api_summary`, `api_inventory`, `api_reports`,
  `api_reports_clear`, `api_reports_export`, `reports_handler`.
- **SSH-ключи:** `api_ssh_keys`, `api_ssh_keys_create`, `api_keys_generate`.
  Хелперы провижининга: `_provision_ssh_key` (`ssh-copy-id` через `sshpass`),
  `_resolve_ssh_key`, `_save_ssh_key`, `_generate_ssh_key`, `_write_generated_ssh_key`,
  `_ssh_fingerprint`, `_install_uploaded_module`.
- `error_middleware`, `index_handler` (легаси-статика из `static/`).

### `auth_middleware.py` — защита маршрутов
- `auth_middleware(request, handler)` — требует валидный токен для всех `/api/*`, кроме
  публичных; `_is_public(path)` — исключения: `login`/`register`/`/healthz`.

### `auth_handlers.py` — публичные эндпоинты аутентификации
- `api_register`, `api_login`, `api_login_verify` (второй шаг 2FA — сверка кода из
  Telegram), `api_logout`, `api_me`, `api_me_update` (self-service смена своего
  имени/пароля → `AuthService.update_profile`). Хелперы 2FA: `_send_login_code`,
  `_mask_telegram`.

### `admin_handlers.py` — админ-API (только суперпользователь)
- Пользователи: `api_admin_users_list/create/update/delete`.
- Доступы: `api_admin_user_modules(+_set)`, `api_admin_user_groups(+_set)`.
- Бэкап/восстановление БД: `api_admin_db_tables`, `api_admin_backup`, `api_admin_restore`
  (+ `_do_backup`, `_restart_backend`); `_require_superuser`, `_user_safe`.

### Сценарии (в `server.py`)
- `api_scenarios_list`, `api_scenarios_create`, `api_scenarios_delete`, `api_scenarios_runs`
  (история), `api_scenarios_run` (запуск **в фоне** → возвращает `run_id`),
  `api_scenarios_run_status` (`GET /api/scenarios/runs/{id}` — статус запуска + `step_runs`
  для живого опроса прогресса/активного шага).

### `board_handlers.py` — доски размещения хостов
- `api_boards_list/create/get/update/delete`, `api_boards_save_layout`; `_board_safe`, `_require_auth`.

### `terminal_handler.py` — веб-терминал (WS `/api/terminal/ws`)
- `api_terminal_ws` — интерактивный shell к хосту через `ssh -tt` + локальный PTY.
  Доступен суперпользователю (любой хост) и **преподавателю на машинах его кабинетов**
  (`host_visible`); чужой хост → 403.

### `domens/history.py` — единая лента истории (API)
- `api_history_entries` (`/api/history`, фильтр `?sources=` + пагинация), `api_history_entry`
  (`/api/history/{id}`), `api_history_types` (реестр сервисов для фронта).
  **Права teacher:** видит только записи, чьи `host_ids` пересекаются с его кабинетами
  (`_entry_host_ids` = `host_id` + `payload['host_ids']`); без привязки к компам — скрыто;
  чужая деталь → 403. Логика записи истории — в `services/history.py`.

### `static/` — легаси статический UI
`index.html`, `app.js`, `styles.css` — старый интерфейс, который сервер отдаёт на `/`.
Актуальный фронтенд — в `frontend/` (Next.js).
