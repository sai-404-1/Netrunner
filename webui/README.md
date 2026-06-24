# webui

Бэкенд-сервер NetRunner на `aiohttp`: REST API под `/api/*`, WebSocket `/ws`,
аутентификация, админ-функции и доски. В проде браузерный трафик идёт через Next.js,
который проксирует API на этот сервер под `/api/python/*`.

## Файлы

### `server.py` — основной сервер и API
Точка сборки приложения и большинство хендлеров.
- `_build_app(app_context)` — собирает `web.Application`, middleware и регистрирует все маршруты.
- `run_web_server(app_context, host, port, open_browser, ping_interval)` — запуск панели.
- Утилиты: `model_to_dict` (сериализация dataclass'ов; **скрывает** `password_encrypted`),
  `_ok`/`_error`/`_json_response`, `_read_json`, `_ctx`, `_safe_int`.
- Фоновые задачи и WebSocket: `_run_background`, `_broadcast_task_update`,
  `websocket_handler`, `_periodic_ping` (демон периодической проверки хостов).
- **Хосты:** `api_hosts`, `api_hosts_create`, `api_hosts_update`, `api_hosts_delete`,
  `api_hosts_check`, `api_hosts_check_all`,
  `api_hosts_reprovision` — заново копирует SSH-ключ на хост (при отвале/удалении ключа),
  используя сохранённый или переданный пароль.
- **Группы:** `api_groups`, `api_groups_create/update/delete/add_host`.
- **Модули:** `api_modules`, `api_modules_create/update/delete`.
- **Задачи:** `api_run` (старт в фоне, возврат `run_id`), `api_run_cancel`,
  `api_task_runs`, `api_task_run_status`, `api_task_templates`, `api_task_runs_clear`.
- **Планировщик:** `api_scheduled`, `api_schedule_create/update/delete`, `api_scheduler_tick`.
- **Инвентаризация/сводка/отчёты:** `api_summary`, `api_inventory`, `api_reports`,
  `api_reports_clear`, `api_reports_export`, `reports_handler`.
- **SSH-ключи:** `api_ssh_keys`, `api_ssh_keys_create`, `api_keys_generate`.
  Хелперы провижининга: `_provision_ssh_key` (`ssh-copy-id` через `sshpass`),
  `_resolve_ssh_key`, `_save_ssh_key`, `_generate_ssh_key`, `_write_generated_ssh_key`,
  `_ssh_fingerprint`, `_install_uploaded_module`.
- `error_middleware`, `index_handler` (легаси-статика из `static/`).

### `auth_middleware.py` — защита маршрутов
- `auth_middleware(request, handler)` — требует валидный токен для всех `/api/*`, кроме
  публичных; `_is_public(path)` — список исключений (login/register).

### `auth_handlers.py` — публичные эндпоинты аутентификации
- `api_register`, `api_login`, `api_logout`, `api_me`.

### `admin_handlers.py` — админ-API (только суперпользователь)
- Пользователи: `api_admin_users_list/create/update/delete`.
- Доступы: `api_admin_user_modules(+_set)`, `api_admin_user_groups(+_set)`.
- Бэкап/восстановление БД: `api_admin_db_tables`, `api_admin_backup`, `api_admin_restore`
  (+ `_do_backup`, `_restart_backend`); `_require_superuser`, `_user_safe`.

### `board_handlers.py` — доски размещения хостов
- `api_boards_list/create/get/update/delete`, `api_boards_save_layout`; `_board_safe`, `_require_auth`.

### `static/` — легаси статический UI
`index.html`, `app.js`, `styles.css` — старый интерфейс, который сервер отдаёт на `/`.
Актуальный фронтенд — в `frontend/` (Next.js).
