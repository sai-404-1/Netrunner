from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

_SAFE_IDENT_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*( (ASC|DESC))?$', re.IGNORECASE)


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_ident(name: str) -> str:
    """Validate that a SQL identifier/order expression is safe (no injection)."""
    if not _SAFE_IDENT_RE.match(name.strip()):
        raise ValueError(f"Unsafe SQL identifier: {name!r}")
    return name.strip()


class BaseRepository:
    model_cls = None
    table_name = ''

    def __init__(self, conn):
        self.conn = conn
        if not self.table_name and self.model_cls is not None:
            self.table_name = self.model_cls.__table__

    def _row_to_model(self, row):
        return self.model_cls.from_row(row) if row is not None else None

    def _fetchone(self, query: str, params: tuple[Any, ...] = ()):
        cur = self.conn.execute(query, params)
        return cur.fetchone()

    def _fetchall(self, query: str, params: tuple[Any, ...] = ()):
        cur = self.conn.execute(query, params)
        return cur.fetchall()

    def all(self, order_by: str = 'id'):
        safe_order = _safe_ident(order_by)
        rows = self._fetchall(f'SELECT * FROM {self.table_name} ORDER BY {safe_order}')
        return [self._row_to_model(row) for row in rows]

    def get(self, item_id: int):
        row = self._fetchone(f'SELECT * FROM {self.table_name} WHERE id = ?', (item_id,))
        return self._row_to_model(row)

    def filter(self, **filters):
        if not filters:
            return self.all()
        safe_keys = [_safe_ident(k) for k in filters.keys()]
        where = ' AND '.join(f'{k} = ?' for k in safe_keys)
        rows = self._fetchall(
            f'SELECT * FROM {self.table_name} WHERE {where} ORDER BY id',
            tuple(filters.values()),
        )
        return [self._row_to_model(row) for row in rows]

    def get_one_by(self, **filters):
        if not filters:
            raise ValueError('get_one_by() requires at least one filter')
        safe_keys = [_safe_ident(k) for k in filters.keys()]
        where = ' AND '.join(f'{k} = ?' for k in safe_keys)
        row = self._fetchone(
            f'SELECT * FROM {self.table_name} WHERE {where} LIMIT 1',
            tuple(filters.values()),
        )
        return self._row_to_model(row)

    def exists(self, **filters) -> bool:
        return self.get_one_by(**filters) is not None

    def create(self, **data):
        columns = [_safe_ident(c) for c in data.keys()]
        placeholders = ', '.join('?' for _ in columns)
        query = f"INSERT INTO {self.table_name} ({', '.join(columns)}) VALUES ({placeholders})"
        cur = self.conn.execute(query, tuple(data[col] for col in data.keys()))
        self.conn.commit()
        return self.get(cur.lastrowid)

    def update(self, item_id: int, **data):
        if not data:
            return self.get(item_id)
        safe_keys = [_safe_ident(k) for k in data.keys()]
        assignments = ', '.join(f'{k} = ?' for k in safe_keys)
        query = f'UPDATE {self.table_name} SET {assignments} WHERE id = ?'
        self.conn.execute(query, tuple(data.values()) + (item_id,))
        self.conn.commit()
        return self.get(item_id)

    def delete(self, item_id: int) -> bool:
        cur = self.conn.execute(f'DELETE FROM {self.table_name} WHERE id = ?', (item_id,))
        self.conn.commit()
        return cur.rowcount > 0
