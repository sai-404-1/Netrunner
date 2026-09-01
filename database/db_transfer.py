"""Гибкое резервное копирование и восстановление базы NetRunner.

Поддерживаются:

Бэкап:
  * полный      — копия всего файла БД (SQLite Online Backup API, см. admin_handlers);
  * по таблицам — пустая схема + строки только выбранных таблиц (export_tables).

Восстановление (merge_database):
  * replace — перезапись записей с тем же id (INSERT OR REPLACE), id сохраняются;
  * append  — дополнение базы: каждая строка вставляется с НОВЫМ id, внешние ключи
              перепривязываются на новые id родителей. При конфликте уникального
              натурального ключа (name/slug/username) значение получает суффикс
              «(копия)», чтобы дубликат мог сосуществовать с оригиналом.

«Классическое» восстановление (полная замена файла БД) живёт в admin_handlers и
здесь не реализуется.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from .schema import create_schema


@dataclass(frozen=True)
class _Table:
    name: str
    # колонка-FK -> имя родительской таблицы (для перепривязки id в режиме append)
    fks: dict[str, str] = field(default_factory=dict)
    # натуральные уникальные колонки (одна колонка) — дедуплицируются суффиксом
    unique: tuple[str, ...] = ()
    # таблица-связка: есть UNIQUE по паре или нет собственного id.
    # такие строки в append вставляются через INSERT OR IGNORE без перепривязки id.
    is_link: bool = False
    has_id: bool = True


# Порядок важен: родители идут раньше детей (топологическая сортировка по FK),
# чтобы в режиме append id родителей были перепривязаны до вставки детей.
TABLES: tuple[_Table, ...] = (
    _Table("ssh_keys", unique=("name",)),
    _Table("groups", unique=("name",)),
    _Table("modules", unique=("slug",)),
    _Table("users", unique=("username",)),
    _Table("hosts", fks={"ssh_key_id": "ssh_keys"}, unique=("name",)),
    _Table("task_templates", fks={"module_id": "modules"}),
    _Table("boards", fks={"owner_user_id": "users"}),
    _Table("inventory_snapshots", fks={"host_id": "hosts"}),
    _Table("task_runs", fks={"template_id": "task_templates", "module_id": "modules"}),
    _Table("scheduled_tasks", fks={"template_id": "task_templates"}),
    _Table("reports", fks={"created_by_task_run_id": "task_runs"}),
    _Table("group_hosts", fks={"group_id": "groups", "host_id": "hosts"}, is_link=True, has_id=False),
    _Table("board_hosts", fks={"board_id": "boards", "host_id": "hosts"}, is_link=True),
    _Table("user_group_access", fks={"user_id": "users", "group_id": "groups"}, is_link=True),
    _Table("user_module_access", fks={"user_id": "users", "module_id": "modules"}, is_link=True),
    _Table("history_entries", fks={"host_id": "hosts"}),
    _Table("host_default_credentials"),
)

ALL_TABLE_NAMES: tuple[str, ...] = tuple(t.name for t in TABLES)


def _existing_tables(conn: sqlite3.Connection, schema: str = "main") -> set[str]:
    rows = conn.execute(
        f"SELECT name FROM {schema}.sqlite_master WHERE type='table'"
    ).fetchall()
    return {r[0] for r in rows}


def _columns(conn: sqlite3.Connection, table: str, schema: str = "main") -> list[str]:
    return [r[1] for r in conn.execute(f"PRAGMA {schema}.table_info({table})").fetchall()]


def list_tables_with_counts(db_path: str) -> list[dict]:
    """Список таблиц NetRunner с количеством строк (для UI выбора таблиц)."""
    conn = sqlite3.connect(db_path)
    try:
        present = _existing_tables(conn)
        result = []
        for name in ALL_TABLE_NAMES:
            if name not in present:
                continue
            count = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
            result.append({"table": name, "rows": count})
        return result
    finally:
        conn.close()


def export_tables(src_path: str, dest_path: str, tables: list[str]) -> list[str]:
    """Создаёт по пути dest_path валидную (полная схема) базу NetRunner, заполняя
    только выбранные таблицы. Возвращает фактически экспортированные таблицы."""
    selected = [name for name in ALL_TABLE_NAMES if name in set(tables)]
    src = sqlite3.connect(src_path)
    dest = sqlite3.connect(dest_path)
    try:
        dest.row_factory = sqlite3.Row
        create_schema(dest)  # полная пустая схема + миграции
        dest.execute("PRAGMA foreign_keys = OFF")
        src_present = _existing_tables(src)
        for name in selected:
            if name not in src_present:
                continue
            dest_cols = _columns(dest, name)
            src_cols = set(_columns(src, name))
            cols = [c for c in dest_cols if c in src_cols]
            if not cols:
                continue
            rows = src.execute(f"SELECT {','.join(cols)} FROM {name}").fetchall()
            if not rows:
                continue
            placeholders = ",".join(["?"] * len(cols))
            dest.executemany(
                f"INSERT INTO {name} ({','.join(cols)}) VALUES ({placeholders})",
                [tuple(r) for r in rows],
            )
        dest.commit()
        return selected
    finally:
        src.close()
        dest.close()


def _insert(conn: sqlite3.Connection, table: str, data: dict, conflict: str = ""):
    cols = list(data.keys())
    placeholders = ",".join(["?"] * len(cols))
    prefix = f"INSERT {conflict} INTO" if conflict else "INSERT INTO"
    sql = f"{prefix} main.{table} ({','.join(cols)}) VALUES ({placeholders})"
    return conn.execute(sql, [data[c] for c in cols])


def _dedupe(conn: sqlite3.Connection, table: str, col: str, value) -> tuple[object, bool]:
    """Возвращает (значение, был_ли_переименован). Если значение занято — добавляет
    суффикс «(копия)» / «(копия N)», пока не станет уникальным."""
    def taken(v) -> bool:
        return conn.execute(
            f"SELECT 1 FROM main.{table} WHERE {col}=? LIMIT 1", (v,)
        ).fetchone() is not None

    if value is None or not taken(value):
        return value, False
    candidate = f"{value} (копия)"
    n = 2
    while taken(candidate):
        candidate = f"{value} (копия {n})"
        n += 1
    return candidate, True


def merge_database(db_path: str, source_path: str, mode: str) -> dict:
    """Сливает данные из source_path в живую базу db_path.

    mode='replace' — INSERT OR REPLACE, id сохраняются.
    mode='append'  — вставка с новым id и перепривязкой внешних ключей.

    Возвращает сводку по таблицам. Внешние ключи отключаются на время операции,
    чтобы порядок и каскады не мешали переносу; целостность обеспечивается
    топологическим порядком таблиц и перепривязкой id.
    """
    if mode not in ("replace", "append"):
        raise ValueError(f"Unsupported merge mode: {mode}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    summary: dict = {"mode": mode, "tables": {}, "renamed": []}
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("ATTACH DATABASE ? AS src", (source_path,))
        src_present = _existing_tables(conn, "src")
        main_present = _existing_tables(conn, "main")

        conn.execute("BEGIN")
        remap: dict[str, dict[int, int]] = {t.name: {} for t in TABLES}

        for spec in TABLES:
            if spec.name not in src_present or spec.name not in main_present:
                continue

            main_cols = _columns(conn, spec.name, "main")
            src_cols = set(_columns(conn, spec.name, "src"))
            cols = [c for c in main_cols if c in src_cols]
            if not cols:
                continue

            rows = conn.execute(f"SELECT {','.join(cols)} FROM src.{spec.name}").fetchall()
            inserted = replaced = skipped = 0

            for row in rows:
                data = {c: row[c] for c in cols}
                old_id = data.get("id") if spec.has_id else None

                # Перепривязка внешних ключей на новые id родителей (если они есть).
                for fk_col, parent in spec.fks.items():
                    val = data.get(fk_col)
                    if val is not None and val in remap.get(parent, {}):
                        data[fk_col] = remap[parent][val]

                if mode == "replace":
                    _insert(conn, spec.name, data, "OR REPLACE")
                    if old_id is not None:
                        remap[spec.name][old_id] = old_id
                    replaced += 1
                    continue

                # mode == append
                if spec.has_id:
                    data.pop("id", None)

                if spec.is_link:
                    # связки/доступы: дублировать пару бессмысленно — INSERT OR IGNORE
                    cur = _insert(conn, spec.name, data, "OR IGNORE")
                    if cur.rowcount and cur.rowcount > 0:
                        inserted += 1
                    else:
                        skipped += 1
                    continue

                # обычная сущность: разрешаем конфликты натуральных уникальных ключей
                for ucol in spec.unique:
                    new_val, renamed = _dedupe(conn, spec.name, ucol, data.get(ucol))
                    data[ucol] = new_val
                    if renamed:
                        summary["renamed"].append(
                            {"table": spec.name, "column": ucol, "value": new_val}
                        )
                cur = _insert(conn, spec.name, data)
                if old_id is not None:
                    remap[spec.name][old_id] = cur.lastrowid
                inserted += 1

            summary["tables"][spec.name] = {
                "source_rows": len(rows),
                "inserted": inserted,
                "replaced": replaced,
                "skipped": skipped,
            }

        conn.execute("COMMIT")
        conn.execute("DETACH DATABASE src")
        return summary
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        try:
            conn.execute("DETACH DATABASE src")
        except Exception:
            pass
        raise
    finally:
        conn.close()
