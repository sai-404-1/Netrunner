from __future__ import annotations

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS ssh_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    private_key_path TEXT NOT NULL,
    public_key_path TEXT,
    key_type TEXT,
    public_key TEXT,
    private_key TEXT,
    fingerprint TEXT,
    has_passphrase INTEGER NOT NULL DEFAULT 0,
    passphrase_hint TEXT,
    created_at TEXT NOT NULL,
    expires_at TEXT,
    is_default INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS hosts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    address TEXT NOT NULL,
    port INTEGER NOT NULL DEFAULT 22,
    username TEXT NOT NULL,
    ssh_key_id INTEGER,
    description TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    last_seen_at TEXT,
    password_encrypted TEXT,
    screenshot_path TEXT,
    screenshot_captured_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (ssh_key_id) REFERENCES ssh_keys(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL DEFAULT 'custom',
    description TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS group_hosts (
    group_id INTEGER NOT NULL,
    host_id INTEGER NOT NULL,
    PRIMARY KEY (group_id, host_id),
    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
    FOREIGN KEY (host_id) REFERENCES hosts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS modules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    module_path TEXT NOT NULL,
    class_name TEXT NOT NULL,
    repo_url TEXT,
    is_builtin INTEGER NOT NULL DEFAULT 0,
    is_enabled INTEGER NOT NULL DEFAULT 1,
    description TEXT,
    schema_json TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS task_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    module_id INTEGER NOT NULL,
    target_type TEXT NOT NULL,
    target_id INTEGER NOT NULL,
    args_json TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    stdout_text TEXT,
    stderr_text TEXT,
    exit_code INTEGER,
    per_host_json TEXT,
    started_at TEXT,
    finished_at TEXT,
    trigger_type TEXT NOT NULL DEFAULT 'manual',
    created_by TEXT,
    FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS inventory_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    host_id INTEGER NOT NULL,
    hostname TEXT,
    os_name TEXT,
    kernel TEXT,
    uptime_seconds INTEGER,
    cpu_model TEXT,
    ram_mb INTEGER,
    disks_total_gb REAL,
    disks_free_gb REAL,
    disks_count INTEGER,
    current_user TEXT,
    package_count INTEGER,
    collected_at TEXT NOT NULL,
    raw_json TEXT,
    FOREIGN KEY (host_id) REFERENCES hosts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS scheduled_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    scenario_id INTEGER,
    target_type TEXT NOT NULL,
    target_id INTEGER NOT NULL,
    run_at TEXT NOT NULL,
    is_enabled INTEGER NOT NULL DEFAULT 1,
    last_run_at TEXT,
    created_at TEXT NOT NULL,
    interval_seconds INTEGER,
    max_runs INTEGER,
    run_count INTEGER NOT NULL DEFAULT 0,
    wait_for_online INTEGER NOT NULL DEFAULT 0,
    days_of_week TEXT NOT NULL DEFAULT '',
    start_min INTEGER,
    end_min INTEGER,
    interval_min INTEGER,
    target_host_ids_json TEXT,
    target_group_ids_json TEXT,
    scenario_ids_json TEXT,
    done_host_ids_json TEXT,
    FOREIGN KEY (scenario_id) REFERENCES scenarios(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    report_type TEXT NOT NULL,
    format TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_id INTEGER,
    file_path TEXT NOT NULL,
    summary_json TEXT,
    created_by_task_run_id INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY (created_by_task_run_id) REFERENCES task_runs(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_hosts_ssh_key_id ON hosts (ssh_key_id);
CREATE INDEX IF NOT EXISTS idx_group_hosts_host_id ON group_hosts (host_id);
CREATE INDEX IF NOT EXISTS idx_modules_slug ON modules (slug);
CREATE INDEX IF NOT EXISTS idx_task_runs_module_id ON task_runs (module_id);
CREATE INDEX IF NOT EXISTS idx_task_runs_target ON task_runs (target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_task_runs_status ON task_runs (status);
CREATE INDEX IF NOT EXISTS idx_inventory_host_id ON inventory_snapshots (host_id);
CREATE INDEX IF NOT EXISTS idx_inventory_collected_at ON inventory_snapshots (collected_at DESC);
CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_run_at ON scheduled_tasks (run_at);
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT,
    password_hash TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    is_superuser INTEGER NOT NULL DEFAULT 0,
    role TEXT NOT NULL DEFAULT 'user',
    token TEXT,
    telegram_chat_id TEXT,
    telegram_username TEXT,
    telegram_link_code TEXT,
    telegram_link_expires TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_group_access (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    group_id INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    UNIQUE(user_id, group_id)
);
CREATE INDEX IF NOT EXISTS idx_uga_user ON user_group_access (user_id);

CREATE TABLE IF NOT EXISTS boards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    owner_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    width INTEGER NOT NULL DEFAULT 1600,
    height INTEGER NOT NULL DEFAULT 900,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS board_hosts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    board_id INTEGER NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
    host_id INTEGER NOT NULL REFERENCES hosts(id) ON DELETE CASCADE,
    x REAL NOT NULL DEFAULT 0,
    y REAL NOT NULL DEFAULT 0,
    UNIQUE(board_id, host_id)
);
CREATE INDEX IF NOT EXISTS idx_bh_board ON board_hosts (board_id);

CREATE INDEX IF NOT EXISTS idx_users_username ON users (username);
CREATE INDEX IF NOT EXISTS idx_reports_type_created_at ON reports (report_type, created_at DESC);

CREATE TABLE IF NOT EXISTS user_module_access (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    module_id INTEGER NOT NULL,
    allowed INTEGER NOT NULL DEFAULT 1,
    UNIQUE(user_id, module_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_uma_user ON user_module_access (user_id);

CREATE TABLE IF NOT EXISTS uploaded_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    original_name TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    uploaded_by TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_uploaded_files_created_at ON uploaded_files (created_at DESC);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trusted_devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    device_id TEXT NOT NULL,
    label TEXT,
    trusted_until TEXT,            -- NULL = доверять бессрочно
    created_at TEXT NOT NULL,
    last_used_at TEXT,
    UNIQUE(user_id, device_id)
);
CREATE INDEX IF NOT EXISTS idx_trusted_devices_user ON trusted_devices (user_id);
"""


def _add_column_if_missing(conn, table: str, column: str, definition: str) -> None:
    """Добавляет колонку в существующую таблицу, если её ещё нет."""
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    existing = {row["name"] for row in rows}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _migrate_ssh_keys(conn) -> None:
    """Добавляет в таблицу ssh_keys поля для хранения контента ключей."""
    _add_column_if_missing(conn, "ssh_keys", "key_type", "TEXT")
    _add_column_if_missing(conn, "ssh_keys", "public_key", "TEXT")
    _add_column_if_missing(conn, "ssh_keys", "private_key", "TEXT")
    _add_column_if_missing(conn, "ssh_keys", "fingerprint", "TEXT")


def _column_names(conn, table: str) -> list[str]:
    return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]


def _migrate_scheduled_tasks(conn) -> None:
    """Перевод расписания с шаблонов-модулей на сценарии + поля recurring-расписания.

    Сначала добавляет недостающие поля повторяемости/ожидания онлайн/расписания,
    затем убирает устаревшую колонку template_id: пересоздаёт scheduled_tasks
    без неё и со ссылкой на scenarios. Старые задачи были привязаны к шаблону
    (одиночному модулю) — сценария-аналога у них нет, поэтому их действие после
    сноса шаблонов неизвестно: такие строки переносятся с scenario_id=NULL и
    отключаются (is_enabled=0), чтобы не «висеть» в расписании без действия.
    Задачи, уже привязанные к сценарию (scenario_id задан), переносятся как есть.
    """
    cols = _column_names(conn, "scheduled_tasks")

    for column, definition in [
        ("description", "TEXT DEFAULT NULL"),
        ("interval_seconds", "INTEGER DEFAULT NULL"),
        ("max_runs", "INTEGER DEFAULT NULL"),
        ("run_count", "INTEGER NOT NULL DEFAULT 0"),
        ("wait_for_online", "INTEGER NOT NULL DEFAULT 0"),
        ("scenario_id", "INTEGER DEFAULT NULL"),
        # recurring-расписание по времени (cron): дни + окно + интервал в минутах
        ("days_of_week", "TEXT NOT NULL DEFAULT ''"),
        ("start_min", "INTEGER DEFAULT NULL"),
        ("end_min", "INTEGER DEFAULT NULL"),
        ("interval_min", "INTEGER DEFAULT NULL"),
        # мульти-выбор цели/сценариев (JSON-массивы id)
        ("target_host_ids_json", "TEXT DEFAULT NULL"),
        ("target_group_ids_json", "TEXT DEFAULT NULL"),
        ("scenario_ids_json", "TEXT DEFAULT NULL"),
        # прогресс wait_for_online по хостам: id хостов, на которых сценарий уже
        # отработал (задача «дожидается» оставшихся офлайн-машин группы)
        ("done_host_ids_json", "TEXT DEFAULT NULL"),
    ]:
        if column not in cols:
            _add_column_if_missing(conn, "scheduled_tasks", column, definition)

    if "template_id" not in _column_names(conn, "scheduled_tasks"):
        # Таблица уже в финальном виде (свежая или уже мигрированная) — нечего чинить.
        return

    conn.execute("""
        CREATE TABLE scheduled_tasks_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            scenario_id INTEGER,
            target_type TEXT NOT NULL,
            target_id INTEGER NOT NULL,
            run_at TEXT NOT NULL,
            is_enabled INTEGER NOT NULL DEFAULT 1,
            last_run_at TEXT,
            created_at TEXT NOT NULL,
            interval_seconds INTEGER,
            max_runs INTEGER,
            run_count INTEGER NOT NULL DEFAULT 0,
            wait_for_online INTEGER NOT NULL DEFAULT 0,
            days_of_week TEXT NOT NULL DEFAULT '',
            start_min INTEGER,
            end_min INTEGER,
            interval_min INTEGER,
            target_host_ids_json TEXT,
            target_group_ids_json TEXT,
            scenario_ids_json TEXT,
            done_host_ids_json TEXT,
            FOREIGN KEY (scenario_id) REFERENCES scenarios(id) ON DELETE CASCADE
        )
    """)
    conn.execute("""
        INSERT INTO scheduled_tasks_new (
            id, name, description, scenario_id, target_type, target_id, run_at,
            is_enabled, last_run_at, created_at, interval_seconds, max_runs, run_count,
            wait_for_online, days_of_week, start_min, end_min, interval_min,
            target_host_ids_json, target_group_ids_json, scenario_ids_json,
            done_host_ids_json
        )
        SELECT
            id, name, description, scenario_id, target_type, target_id, run_at,
            CASE WHEN scenario_id IS NOT NULL THEN is_enabled ELSE 0 END,
            last_run_at, created_at, interval_seconds, max_runs, run_count,
            wait_for_online, days_of_week, start_min, end_min, interval_min,
            target_host_ids_json, target_group_ids_json, scenario_ids_json,
            NULL
        FROM scheduled_tasks
    """)
    conn.execute("DROP TABLE scheduled_tasks")
    conn.execute("ALTER TABLE scheduled_tasks_new RENAME TO scheduled_tasks")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_run_at ON scheduled_tasks (run_at)"
    )


def _migrate_task_runs(conn) -> None:
    """Полный снос task_templates: убирает колонку template_id из task_runs.

    Раньше задача (запуск модуля) была привязана к шаблону (task_templates)
    через task_runs.template_id. Таблица task_templates удалена, шаблоны-модули
    заменены на сценарии (scenario_id в scheduled_tasks). Поэтому пересоздаёт
    task_runs без колонки template_id и связанного FK-каскада (ON DELETE
    SET NULL). Данные о прошлых запусках модулей (module_id, вывод, статусы)
    не теряются — теряется только ссылка на удалённый шаблон, которая больше
    нигде не используется (кроме legacy-статики, которая выпиливается).
    """
    if "template_id" not in _column_names(conn, "task_runs"):
        # Таблица уже без template_id (свежая или уже мигрированная) — нечего чинить.
        return

    conn.execute("""
        CREATE TABLE task_runs_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_id INTEGER NOT NULL,
            target_type TEXT NOT NULL,
            target_id INTEGER NOT NULL,
            args_json TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            stdout_text TEXT,
            stderr_text TEXT,
            exit_code INTEGER,
            per_host_json TEXT,
            started_at TEXT,
            finished_at TEXT,
            trigger_type TEXT NOT NULL DEFAULT 'manual',
            created_by TEXT,
            FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE CASCADE
        )
    """)
    conn.execute("""
        INSERT INTO task_runs_new (
            id, module_id, target_type, target_id, args_json, status,
            stdout_text, stderr_text, exit_code, per_host_json,
            started_at, finished_at, trigger_type, created_by
        )
        SELECT
            id, module_id, target_type, target_id, args_json, status,
            stdout_text, stderr_text, exit_code, per_host_json,
            started_at, finished_at, trigger_type, created_by
        FROM task_runs
    """)
    conn.execute("DROP TABLE task_runs")
    conn.execute("ALTER TABLE task_runs_new RENAME TO task_runs")
    for index in ("idx_task_runs_module_id", "idx_task_runs_target", "idx_task_runs_status"):
        conn.execute(
            f"CREATE INDEX IF NOT EXISTS {index} ON task_runs "
            "(" + {"idx_task_runs_module_id": "module_id",
                   "idx_task_runs_target": "target_type, target_id",
                   "idx_task_runs_status": "status"}[index] + ")"
        )
    # Окончательно сносим таблицу шаблонов-модулей и её индекс (для существующих БД,
    # где она уже была создана). Новые БД её вообще не создают (убран CREATE TABLE).
    conn.execute("DROP TABLE IF EXISTS task_templates")
    conn.execute("DROP INDEX IF EXISTS idx_task_templates_module_id")


def _migrate_users(conn) -> None:
    _add_column_if_missing(conn, "users", "role", "TEXT NOT NULL DEFAULT 'user'")
    _add_column_if_missing(conn, "users", "telegram_chat_id", "TEXT")
    _add_column_if_missing(conn, "users", "telegram_username", "TEXT")
    _add_column_if_missing(conn, "users", "telegram_link_code", "TEXT")
    _add_column_if_missing(conn, "users", "telegram_link_expires", "TEXT")


def _migrate_modules(conn) -> None:
    _add_column_if_missing(conn, "modules", "schema_json", "TEXT")


def _migrate_hosts(conn) -> None:
    """Хранит зашифрованный пароль хоста для повторной привязки SSH-ключа."""
    _add_column_if_missing(conn, "hosts", "password_encrypted", "TEXT")
    _add_column_if_missing(conn, "hosts", "screenshot_path", "TEXT")
    _add_column_if_missing(conn, "hosts", "screenshot_captured_at", "TEXT")


def _create_new_tables(conn) -> None:
    conn.executescript("""
CREATE TABLE IF NOT EXISTS user_group_access (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    group_id INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    UNIQUE(user_id, group_id)
);
CREATE INDEX IF NOT EXISTS idx_uga_user ON user_group_access (user_id);

CREATE TABLE IF NOT EXISTS boards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    owner_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    width INTEGER NOT NULL DEFAULT 1600,
    height INTEGER NOT NULL DEFAULT 900,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS board_hosts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    board_id INTEGER NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
    host_id INTEGER NOT NULL REFERENCES hosts(id) ON DELETE CASCADE,
    x REAL NOT NULL DEFAULT 0,
    y REAL NOT NULL DEFAULT 0,
    UNIQUE(board_id, host_id)
);
CREATE INDEX IF NOT EXISTS idx_bh_board ON board_hosts (board_id);

CREATE TABLE IF NOT EXISTS scenarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    target_type TEXT NOT NULL DEFAULT 'group',
    target_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scenario_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_id INTEGER NOT NULL,
    module_id INTEGER NOT NULL,
    step_order INTEGER NOT NULL,
    step_name TEXT,
    config_json TEXT NOT NULL DEFAULT '{}',
    depends_on_step_id INTEGER,
    on_failure TEXT NOT NULL DEFAULT 'stop',
    retry_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (scenario_id) REFERENCES scenarios(id) ON DELETE CASCADE,
    FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE CASCADE,
    FOREIGN KEY (depends_on_step_id) REFERENCES scenario_steps(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS scenario_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_id INTEGER NOT NULL,
    target_type TEXT NOT NULL,
    target_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    started_at TEXT,
    finished_at TEXT,
    trigger_type TEXT NOT NULL DEFAULT 'manual',
    FOREIGN KEY (scenario_id) REFERENCES scenarios(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS scenario_step_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_run_id INTEGER NOT NULL,
    step_id INTEGER NOT NULL,
    host_id INTEGER NOT NULL,
    module_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    output_text TEXT,
    error_text TEXT,
    exit_code INTEGER,
    started_at TEXT,
    finished_at TEXT,
    FOREIGN KEY (scenario_run_id) REFERENCES scenario_runs(id) ON DELETE CASCADE,
    FOREIGN KEY (step_id) REFERENCES scenario_steps(id) ON DELETE CASCADE,
    FOREIGN KEY (host_id) REFERENCES hosts(id) ON DELETE CASCADE,
    FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_scenario_steps_scenario ON scenario_steps (scenario_id);
CREATE INDEX IF NOT EXISTS idx_scenario_runs_scenario ON scenario_runs (scenario_id);
CREATE INDEX IF NOT EXISTS idx_scenario_step_runs_run ON scenario_step_runs (scenario_run_id);

-- Endpoint-агент хоста: report-only, сам открывает исходящее WS-соединение к
-- серверу (звонит домой) — на хосте не нужно открывать порты, сервер не лезет
-- внутрь. Отдельный сервисный SSH-пользователь + ключ — канал восстановления
-- через уже существующий SSH, если агент/токен когда-нибудь потребуется
-- перевыпустить, и отдельный bearer-токен для самого WS-соединения: разные
-- секреты для разных целей, компрометация одного не вскрывает другой.
CREATE TABLE IF NOT EXISTS host_agents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    host_id INTEGER NOT NULL UNIQUE REFERENCES hosts(id) ON DELETE CASCADE,
    ssh_username TEXT NOT NULL,
    token_encrypted TEXT NOT NULL,
    private_key_encrypted TEXT NOT NULL,
    public_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'provisioned',
    last_seen_at TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_host_agents_host ON host_agents (host_id);

-- Таймлайн статусных событий хоста, наполняется агентом. type — открытый набор
-- (heartbeat, online, в будущем что угодно ещё): сервер журналирует событие как
-- есть, добавление нового типа не требует изменений схемы или кода сервера.
CREATE TABLE IF NOT EXISTS host_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    host_id INTEGER NOT NULL REFERENCES hosts(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    payload_json TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_host_events_host ON host_events (host_id, created_at);

-- Журнал внутренних процессов сервера («История» → «Логи»): попытки автоустановки
-- агента и т.п. Не путать с host_events (статусы ОТ агента) или task_runs (запуски
-- модулей пользователем) — это ход работы самого сервера.
CREATE TABLE IF NOT EXISTS system_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    level TEXT NOT NULL DEFAULT 'info',
    message TEXT NOT NULL,
    host_id INTEGER REFERENCES hosts(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_system_logs_created ON system_logs (created_at);

-- Единая лента «История»: общий журнал сервисных событий NetRunner. Сюда пишут
-- все сервисы (сценарии, TaskRunner, агент, планировщик) через HistoryService.
-- НЕ путать с system_logs (программные логи кода) или task_runs/scenario_runs
-- (рабочие таблицы исполнения). source — slug зарегистрированного сервиса
-- (scenario/task/agent/agent_message/scheduler), payload_json — специфичные поля,
-- которые сервис сам решил записать (колонки из его реестра).
CREATE TABLE IF NOT EXISTS history_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    event_type TEXT NOT NULL,
    actor_name TEXT,
    actor_id INTEGER,
    title TEXT NOT NULL,
    description TEXT,
    level TEXT NOT NULL DEFAULT 'info',
    payload_json TEXT,
    ref_type TEXT,
    ref_id INTEGER,
    host_id INTEGER REFERENCES hosts(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_history_entries_created ON history_entries (created_at);
CREATE INDEX IF NOT EXISTS idx_history_entries_source ON history_entries (source);

CREATE TABLE IF NOT EXISTS host_default_credentials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    password_encrypted TEXT NOT NULL,
    last_updated_at TEXT NOT NULL
);
""")

def create_schema(conn) -> None:
    conn.executescript(SCHEMA_SQL)
    _migrate_ssh_keys(conn)
    _migrate_scheduled_tasks(conn)
    _migrate_task_runs(conn)
    _migrate_users(conn)
    _migrate_modules(conn)
    _migrate_hosts(conn)
    _create_new_tables(conn)
    conn.commit()
