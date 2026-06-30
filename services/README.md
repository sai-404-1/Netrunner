# services

Бизнес-логика NetRunner: сборка контекста приложения, исполнение задач, планировщик,
аутентификация, реестр модулей, отчёты, работа с хостами и шифрование секретов.

## Файлы

### `app_context.py` — узел связывания всего приложения
- `class AppContext` — держит БД, все сервисы, реестр модулей, task-runner, планировщик,
  auth и отчёты (`close()` закрывает ресурсы).
- `create_app_context(db_path, reports_dir, run_scheduler_on_start)` — собирает единый
  `AppContext` для CLI или web-GUI: открывает/мигрирует БД, регистрирует встроенные и
  пользовательские модули, грузит модули с диска, сидит шаблоны задач, создаёт пользователя
  `admin/admin`, прогоняет один тик планировщика.
- `bootstrap_database(db, host_service)` — первичная подготовка БД и импорт legacy `hosts.json`.
- `bootstrap_task_templates(db)` — создание базовых шаблонов задач.
- `_load_user_modules_from_disk(module_registry)` — загрузка модулей из `/app/modules` (или `modules/`).

### `host_service.py` — работа с хостами
- `class HostService`:
  - CRUD/выборки: `all_hosts`, `active_hosts`, `get_host`, `add_host(..., password=)`,
    `remove_host`, `import_legacy_hosts_json`.
  - Пароли хостов: `set_host_password(host_id, password)` (шифрует),
    `get_host_password(host_id)` (расшифровывает) — для повторной привязки SSH-ключа.
  - Группы: `create_group`, `add_host_to_group`, `group_hosts`, `resolve_targets`.
  - SSH: `to_computer(host)`/`to_computers(hosts)` — строит фасад `Computer`.
  - Проверка: `check_host`/`async check_host_async`, `check_all_hosts`/`async check_all_hosts_async`.

### `secrets.py` — шифрование секретов хостов
Обратимое шифрование паролей для повторной привязки ключа. Своя соль на каждую запись,
ключ Fernet выводится из мастер-ключа (env `NETRUNNER_SECRET_KEY` или файл `data/.secret_key`)
через PBKDF2-HMAC-SHA256.
- `encrypt_secret(plaintext)` → строка `base64(соль):fernet_token`.
- `decrypt_secret(stored)` → исходный пароль.
- `_load_master_secret()`, `_fernet_for_salt(salt)` — служебные.

### `task_runner.py` — исполнение модулей по целям
- `class ModuleContext` — контекст, передаваемый модулю (несёт `logger`, `task_run_id`,
  `to_computer` и `db` — модуль может резолвить данные, напр. загруженные файлы).
- `class TaskRunner` — async-first исполнение по хостам с отменой:
  - `run(...)` / `async run_async(...)` — запуск модуля по `host`/`group`;
  - `run_template(...)` / `async run_template_async(...)` — запуск по шаблону;
  - `cancel(run_id)` — отмена одного/всех запусков;
  - `_run_per_host` — конкурентное исполнение `run_for_host` через `asyncio.as_completed`;
    результаты по хостам пишутся в `per_host_json` **инкрементально** (`_save_progress`)
    для живого прогресса; число одновременных хостов ограничивается семафором, если у
    модуля задан `max_parallel` (напр. рассылка файлов).

### `scheduler.py` — планировщик
- `class Scheduler`: `tick()` / `async tick_async()` — найти просроченные задачи и запустить их.

### `scenario_runner.py` — исполнение сценариев (цепочек модулей)
- `class ScenarioRunner`: `run_scenario_async(scenario_id, target_type, target_id, trigger_type, scenario_run_id=None)`
  — последовательно прогоняет шаги сценария, каждый шаг — по хостам конкурентно
  (семафор), пишет live-статусы в `scenario_step_runs` (running → completed/failed) и
  `scenario_runs`. Параметр `scenario_run_id` позволяет переиспользовать заранее
  созданную run-строку (фоновый запуск через API с немедленным возвратом `run_id`).

### `module_registry.py` — реестр модулей
- `class RegisteredModule` — обёртка над runtime-экземпляром модуля.
- `class ModuleRegistry` — сводит builtin/пользовательские/дисковые модули в одно место и
  зеркалит их в таблицу `modules`: `register_instance`, `register_menu_items`, `get(slug)`,
  `all()`, `menu_items(...)`, `_slugify`.

### `auth_service.py` — аутентификация
- `class AuthService`: `register`, `login`, `logout`, `me(token)`, `create_default_user`,
  `update_profile(user_id, new_username, current_password, new_password)` — self-service
  смена своего имени/пароля (смена пароля требует подтверждения текущим).
- Хелперы: `_hash_password`/`_verify_password` (PBKDF2-SHA256), `create_access_token`.

### `telegram_service.py` — привязка/верификация Telegram (фундамент 2FA)
- `class TelegramService(db)`: токен бота в `app_settings` (шифр) или env
  `NETRUNNER_TELEGRAM_BOT_TOKEN`. `create_link_code(user)` — код + ссылка
  `t.me/<bot>?start=<code>`; `poll_once()` — getUpdates, ловит `/start <code>` и
  привязывает `chat_id` к пользователю; `status`/`unlink`/`send_message`/`get_bot_username`.
  Фоновый поллер — `_telegram_poller` в `webui/server.py`.

### `update_service.py` — самообновление кода через git (Phase 2)
- `class UpdateService(db)` — хранит конфиг в таблице `app_settings` (git-remote, ветка,
  deploy-токен в шифре, интервал, авто-флаг):
  - `get_config()` / `set_config(...)` — чтение/запись конфига (токен шифруется через `secrets.py`);
  - `check()` — `git fetch` + сравнение HEAD с `origin/<branch>` (behind-count), read-only;
  - `apply()` — снимок БД (`netrunner.db.pre_update`) + `git reset --hard origin/<branch>` +
    маркер `.updating`; реальный перезапуск/пересборку делает супервизор (`supervise.py`).
  - git-операции — graceful no-op без git-чекаута.

### `report_service.py` — генерация отчётов
- `class ReportService` — экспорт в TXT/CSV/JSON: `export_task_runs`, `export_inventory`,
  `export_host_status`, `export_filesystem`, `export_task_history`, `export_from_task_run`
  плюс приватные writer'ы `_write_*`.

### `menu_actions.py` — действия интерактивного TUI-меню
Набор классов `*Action` (наследники `MenuAction`) для CLI-меню: показать хосты/группы/
модули/историю/планировщик/отчёты/инвентаризацию, запустить модуль, создать запланированную
задачу, экспортировать отчёт. Плюс утилиты форматирования таблиц (`print_table`,
`format_dt`, `status_ru` и др.).
