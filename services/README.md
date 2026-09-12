# services

Бизнес-логика NetRunner: сборка контекста приложения, исполнение задач, планировщик,
аутентификация, реестр модулей, отчёты, работа с хостами и шифрование секретов.

## Файлы

### `app_context.py` — узел связывания всего приложения
- `class AppContext` — держит БД, все сервисы, реестр модулей, task-runner, планировщик,
  auth и отчёты (`close()` закрывает ресурсы).
- `create_app_context(db_path, reports_dir, run_scheduler_on_start)` — собирает единый
  `AppContext` для CLI или web-GUI: открывает/мигрирует БД, регистрирует встроенные и
  пользовательские модули, грузит модули с диска, создаёт пользователя `admin/admin`,
  прогоняет один тик планировщика.
- `bootstrap_database(db, host_service)` — первичная подготовка БД и импорт legacy `hosts.json`.
- `_load_user_modules_from_disk(module_registry)` — загрузка модулей из `/app/modules` (или `modules/`).

### `host_service.py` — работа с хостами
- `class HostService`:
  - CRUD/выборки: `all_hosts`, `active_hosts`, `get_host`, `add_host(..., password=)`,
    `remove_host`, `import_legacy_hosts_json`.
  - Пароли хостов: `set_host_password(host_id, password)` (шифрует),
    `get_host_password(host_id)` (расшифровывает) — для повторной привязки SSH-ключа.
  - Группы: `create_group`, `add_host_to_group`, `group_hosts`, `resolve_targets`,
    `resolve_scheduled_targets(host_ids, group_ids)` — раскрытие мульти-выбора цели
    планировщика в список хостов (группы → их хосты, дедуп).
  - SSH: `to_computer(host)`/`to_computers(hosts)` — строит фасад `Computer`.
    Пользователь исполнения берётся из глобальной настройки
    `execution_settings.ssh_user_mode`: `service` → `netrunner-svc` (ключ агента),
    `primary` → первичный пользователь хоста (`host.username`). Настройка
    перечитывается на каждом вызове, на хостах ничего не меняется.
    `to_computer_bootstrap(host)` — всегда первичный пользователь (проверка
    доступности, первичная установка агента).
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

### `scheduler.py` — планировщик (исполняет только сценарии)
- `class Scheduler(db, scenario_runner, logger, history, host_service)` — планировщик
  запланированных задач. Каждая задача привязана к **сценарию** (`scenario_id`), шаблоны
  из планировщика убраны.
  - `tick()` — синхронная обёртка над `tick_async()` через `asyncio.run` (для старта
    сервера и CLI/TUI вне event loop).
  - `async tick_async()` — главный тик: `db.scheduled.due()` → каждую due-задачу запускает
    через `scenario_runner.run_scenario_async(..., trigger_type="scheduled")`, затем
    `mark_ran`. Фоновый цикл крутит его в `server/server.py` раз в 60 секунд.
  - Триггеры задачи (см. `schedule_repo`): разовый по времени, recurring-расписание
    (дни недели + окно «С…До» + интервал), ожидание сети (`wait_for_online`).
  - Для recurring-слота при офлайн-цели слот **пропускается** (запись в историю
    `scheduler_skip` «цель не в сети»), `run_at` сдвигается на следующий слот — без
    «догонялок» (для выполнения по факту включения есть отдельный режим wait_for_online).
  - **`wait_for_online` — пер-хост (`_run_wait_for_online`):** группа не выступает
    единой целью, а раскрывается в конкретные хосты. «Просыпается» по первому
    онлайн-хосту, но сценарий выполняет **только на тех, что сейчас в сети**; хосты,
    до которых не достучались, продолжают ждать (прогресс — `scheduled_tasks.
    done_host_ids_json`). Когда покрыты все хосты цели — задача закрывается
    (`mark_ran`). Правка задачи сбрасывает прогресс.

### `scenario_runner.py` — исполнение сценариев (цепочек модулей)
- `class ScenarioRunner` — асинхронный прогон многошаговых сценариев **пер-хост**: у каждого
  компьютера своя очередь шагов, падение хоста уводит с дистанции только его (`on_failure`
  `stop`/`continue`). Результаты пишутся в `scenario_step_runs` (running → completed/failed/
  skipped) и агрегируются в `scenario_runs`.
  - `run_scenario_async(scenario_id, target_type, target_id, trigger_type, scenario_run_id)` —
    запуск одного сценария.
  - `run_scenarios_async(scenario_ids, ...)` — очередь сценариев на одну цель.
  - Темп выполнения (`execution_settings`): пакетами (`MODE_BATCH`) или с ограничением
    параллелизма; шаги-модули резолвятся заранее (`_StepPlan`) — недоступный модуль —
    ошибка шага, а не падение всего запуска.
  - **Coldawn** (`_run_scenario_on_host_with_coldawn`): если сценарий не смог даже
    начаться на хосте (первый шаг не выполнился — отказ SSH/сети на старте), запуск
    повторяется до `execution_settings.coldawn_retries` раз с паузой `COLDAWN_RETRY_DELAY`.
    Исчерпали — в историю пишется факт `scenario_coldawn` (warning), машина пропускается,
    очередь идёт к следующей. Логируется только факт исчерпания, не каждый повтор.

### `module_registry.py` — реестр модулей
- `class RegisteredModule` — обёртка над runtime-экземпляром модуля.
- `class ModuleRegistry` — сводит builtin/пользовательские/дисковые модули в одно место и
  зеркалит их в таблицу `modules`: `register_instance`, `register_menu_items`, `get(slug)`,
  `all()`, `menu_items(...)`, `_slugify`.

### `auth_service.py` — аутентификация + 2FA
- `class AuthService`: `register`, `login`, `logout`, `me(token)`, `create_default_user`,
  `update_profile(user_id, new_username, current_password, new_password)` — self-service
  смена своего имени/пароля (смена пароля требует подтверждения текущим).
- **2FA (step-up через Telegram):** если у пользователя привязан Telegram и вход идёт с
  недоверенного устройства, `login(..., device_id)` не выдаёт токен, а создаёт одноразовый
  код (челлендж в памяти процесса) и возвращает `mfa_required`. `verify_challenge(
  challenge_id, code, device_id, trust)` сверяет код (TTL 5 мин, до 5 попыток), выдаёт
  токен и по флагу `trust` доверяет устройству на 1 час. Управление доверенными
  устройствами: `is_device_trusted`, `list_trusted_devices`, `set_device_trust(forever=)`,
  `revoke_device`. Хранилище доверия — таблица `trusted_devices` (`db.trusted_devices`).
- Хелперы: `_hash_password`/`_verify_password` (PBKDF2-SHA256), `create_access_token`,
  `_issue_token`, `_create_challenge`.

### `telegram_service.py` — привязка/верификация Telegram (фундамент 2FA)
- `class TelegramService(db)`: токен бота в `app_settings` (шифр) или env
  `NETRUNNER_TELEGRAM_BOT_TOKEN`. `create_link_code(user)` — код + ссылка
  `t.me/<bot>?start=<code>`; `poll_once()` — getUpdates, ловит `/start <code>` и
  привязывает `chat_id` к пользователю; `status`/`unlink`/`send_message`/`get_bot_username`.
  Фоновый поллер — `_telegram_poller` в `../server/server.py`.

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

### `history.py` — единая история событий
- `class HistoryService` — общая лента событий NetRunner. Сервисы регистрируются с
  реестром (`slug`, имя, колонки, типы событий): `scenario`, `task`, `agent`,
  `agent_message`, `scheduler`. Единая точка записи — `record(source, event_type, title, ...)`
  → строка в `history_entries` (общая лента в UI). Чтение: `list(limit, sources, offset)`,
  `count(sources)`. События сценария: `scenario_run`, `scenario_run_done` (success),
  `scenario_run_partial` (**warning** — часть машин прошла, часть нет; НЕ ошибка),
  `scenario_step_failed`, `scenario_failed`, `scenario_coldawn` (warning — запуск
  не удалось начать после повторов, машина пропущена).

### `execution_settings.py` — настройки исполнения (темп + пользователь)
- `class ExecutionSettings(db)` — глобальные настройки исполнения на сервере:
  - темп «как гнать хосты»: режим пакетами (`MODE_BATCH`, `batch_size`, `batch_delay`)
    либо с ограничением параллелизма (`max_parallel`);
  - **пользователь исполнения** `ssh_user_mode`: `service` (`netrunner-svc`, дефолт)
    либо `primary` (первичный пользователь хоста) — влияет на `HostService.to_computer`;
  - **повторы запуска** `coldawn_retries`: сколько раз повторить запуск, если сценарий
    не смог начаться (по умолчанию 3, 0 — выключено) — читает `ScenarioRunner`.
  - `FIELDS` — единственный источник правды (ключ в `app_settings`, дефолт, границы,
    подпись для формы); `get_config`/`set_config`/`schema`. Перечитывается перед каждым
    запуском; меняется со страницы «Администрирование».

### `agent_service.py` — обслуживание endpoint-агента
- `class AgentService` — жизненный цикл endpoint-агента на управляемой машине:
  провижининг/переустановка (под первичным пользователем через `netrunner-svc`,
  `sudoers.d` с root), `get_existing` — определение режима переустановки без ротации
  ключа/токена, конфиг WS-адреса (`NETRUNNER_AGENT_WS_URL` в Docker).

### `menu_actions.py` — действия интерактивного TUI-меню
Набор классов `*Action` (наследники `MenuAction`) для CLI-меню: показать хосты/группы/
модули/историю/планировщик/отчёты/инвентаризацию, запустить модуль, создать запланированную
задачу, экспортировать отчёт. Плюс утилиты форматирования таблиц (`print_table`,
`format_dt`, `status_ru` и др.).
