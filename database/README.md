# database

Лёгкий ORM-подобный слой для NetRunner на базе `sqlite3`.

## Что внутри
- `schema.py` — создание таблиц и индексов;
- `models/` — dataclass-модели;
- `repos/` — CRUD и специальные запросы;
- `orm.py` — класс `Database` с удобным доступом: `db.hosts.all()`, `db.groups.add_host(...)`.

## Быстрый старт
```python
from database import open_database

db = open_database('data/netrunner.db')

key = db.ssh_keys.create(
    name='default',
    private_key_path='keys/id_ed25519',
    public_key_path='keys/id_ed25519.pub',
    is_default=1,
)

host = db.hosts.create(
    name='pc-101-01',
    address='192.168.0.10',
    username='student',
    ssh_key_id=key.id,
)
```

## Legacy import
```python
count = db.import_legacy_hosts_json('hosts.json', ssh_key_id=key.id)
```

## Файлы

### `__init__.py`
Реэкспорт `open_database`/`init_database`.

### `connection.py`
- `connect(db_path)` — открывает соединение `sqlite3` с нужными PRAGMA (row_factory и т.п.).

### `schema.py` — схема и миграции
Полный `CREATE TABLE` SQL **и** идемпотентные миграции. При добавлении колонки в
существующую таблицу её нужно прописывать и в `CREATE TABLE`, и в миграцию.
- `create_schema(conn)` — создаёт таблицы/индексы и прогоняет все миграции.
- `_add_column_if_missing(conn, table, column, definition)` — добавить колонку, если её нет.
- `_migrate_ssh_keys/_migrate_scheduled_tasks/_migrate_users/_migrate_modules/_migrate_hosts(conn)`
  — точечные миграции таблиц (например, `_migrate_hosts` добавляет `password_encrypted`
  — зашифрованный пароль хоста для повторной привязки SSH-ключа).
- `_create_new_tables(conn)` — досоздаёт новые таблицы (`user_group_access`, `boards`, `board_hosts`).
- В `SCHEMA_SQL` также есть таблицы `uploaded_files` (загруженные файлы для рассылки),
  `app_settings` (key/value-настройки, в т.ч. конфиг самообновления) и `trusted_devices`
  (доверенные устройства для 2FA через Telegram).

### `orm.py` — фасад `Database`
- `class Database` — открывает соединение, прогоняет `create_schema`, предоставляет
  по одному репозиторию на таблицу как атрибут (`db.hosts`, `db.modules`, `db.users`, …).
  Методы: `model(name)`, `commit()`, `close()`, `import_legacy_hosts_json(path, ssh_key_id)`.
- `init_database(db_path)` / `open_database(db_path)` — фабрики соединения.

### `db_transfer.py` — резервное копирование и восстановление
- `list_tables_with_counts(db_path)` — список таблиц NetRunner с числом строк (для UI).
- `export_tables(src_path, dest_path, tables)` — выгрузка выбранных таблиц в валидную
  (полная схема) базу.
- `merge_database(db_path, source_path, mode)` — слияние данных из другой базы в живую.
- Вспомогательные: `_existing_tables`, `_columns`, `_insert`, `_dedupe`.

## Подпапки
- `models/` — dataclass-модели строк таблиц. См. `models/README.md`.
- `repos/` — репозитории (CRUD и специальные запросы). См. `repos/README.md`.
