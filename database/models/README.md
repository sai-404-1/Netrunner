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
- `scheduled_task.py` — `ScheduledTask`: запланированная задача (время, интервал, лимит запусков).
- `inventory_snapshot.py` — `InventorySnapshot`: снимок инвентаризации хоста (ОС, RAM, диски и т.д.).
- `report.py` — `Report`: сгенерированный отчёт (тип, формат, путь к файлу).
- `user.py` — `User`: пользователь (логин, хэш пароля, роль, токен, флаги активности/суперпользователя).
- `user_group_access.py` — `UserGroupAccess`: доступ пользователя к группе.
- `user_module_access.py` — `UserModuleAccess`: доступ пользователя к модулю.
- `board.py` — `Board`: доска для визуального размещения хостов.
- `board_host.py` — `BoardHost`: позиция хоста на доске (x, y).
