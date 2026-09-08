# database/models

Dataclass-модели строк таблиц NetRunner. Каждая модель — это «строка» соответствующей
таблицы; репозитории в `database/repos/` возвращают именно эти объекты.

## Базовый класс

### `base.py`
- `class BaseModel` — общий предок всех моделей.
  - `__table__` / `__pk__` — имя таблицы и первичного ключа.
  - `columns(include_pk)` — список колонок.
  - `from_row(row)` — собрать модель из строки `sqlite3.Row` (берёт только известные поля).
  - `to_record(include_pk)` — представить модель как dict для записи в БД.

## Модели (одна на таблицу)

- `host.py` — `Host`: управляемый узел (имя, адрес, порт, пользователь, `ssh_key_id`,
  `password_encrypted` — зашифрованный пароль, `is_active`, `last_seen_at`).
- `ssh_key.py` — `SSHKey`: SSH-ключ (пути/контент приватной и публичной части, fingerprint,
  флаг `is_default`).
- `group.py` — `Group`: группа хостов.
- `group_host.py` — `GroupHost`: связь many-to-many группа↔хост.
- `module_record.py` — `ModuleRecord`: запись о модуле (slug, схема, builtin/enabled).
- `task_template.py` — `TaskTemplate`: шаблон задачи (модуль + аргументы по умолчанию).
- `task_run.py` — `TaskRun`: запуск задачи (статус, stdout/stderr, `per_host_json`, кто запустил).
- `scheduled_task.py` — `ScheduledTask`: запланированная задача, привязанная к **сценарию**
  (`scenario_id`), с целью, `run_at` (UTC-слот) и описанием (`description`). Варианты условия:
  разовая по времени; recurring-**расписание** (`days_of_week` — 7-битмаска, `start_min`/
  `end_min`/`interval_min` — окно «С…До» и интервал); ожидание сети (`wait_for_online`).
- `inventory_snapshot.py` — `InventorySnapshot`: снимок инвентаризации хоста (ОС, RAM, диски и т.д.).
- `report.py` — `Report`: сгенерированный отчёт (тип, формат, путь к файлу).
- `user.py` — `User`: пользователь (логин, хэш пароля, роль, токен, флаги активности/
  суперпользователя, поля привязки Telegram для 2FA).
- `trusted_device.py` — `TrustedDevice`: доверенное устройство пользователя для 2FA
  (`device_id`, `label`, `trusted_until` — `NULL` = бессрочно, `last_used_at`). Таблица
  `trusted_devices`.
- `user_group_access.py` — `UserGroupAccess`: доступ пользователя к группе.
- `user_module_access.py` — `UserModuleAccess`: доступ пользователя к модулю.
- `board.py` — `Board`: доска для визуального размещения хостов.
- `board_host.py` — `BoardHost`: позиция хоста на доске (x, y).
- `uploaded_file.py` — `UploadedFile`: загруженный файл для рассылки (имя, путь на диске,
  размер, кто загрузил). Таблица `uploaded_files`.
- `scenario.py` — `Scenario`/`ScenarioStep`/`ScenarioRun`/`ScenarioStepRun`: сценарии
  (цепочки модулей) и их запуски (добавлены отдельной фичей).
- `host_agent.py` — `HostAgent`: провиженный endpoint-агент хоста (report-only, сам звонит
  по WS): `ssh_username`, зашифрованные `token_encrypted`/`private_key_encrypted`,
  `public_key`, `status`, `last_seen_at`.
- `host_event.py` — `HostEvent`: событие хоста от агента (`online`/`heartbeat`/…), таймлайн.
- `history_entry.py` — `HistoryEntry`: строка единой истории событий NetRunner
  (`source`, `event_type`, `title`, `payload`, ссылки).
- `system_log.py` — `SystemLog`: журнал внутренних процессов сервера.
- `host_default_cred.py` — `HostDefaultCred`: стандартные учётные данные (username/пароль
  в шифре) для быстрой добавки новых хостов.

> Таблица `app_settings` (key/value-настройки, напр. конфиг самообновления) модели не
> имеет — с ней работают напрямую через `db.app_settings` (см. `repos/app_settings_repo.py`).
