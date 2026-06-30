from __future__ import annotations

from .base import BaseRepository, utcnow_iso


class AppSettingsRepo(BaseRepository):
    """Простое key/value-хранилище настроек приложения (таблица app_settings)."""

    table_name = "app_settings"
    model_cls = None  # работаем напрямую со значениями, без dataclass-модели

    def get(self, key: str, default: str | None = None) -> str | None:
        row = self._fetchone("SELECT value FROM app_settings WHERE key = ?", (key,))
        return row["value"] if row is not None else default

    def set(self, key: str, value: str | None) -> None:
        self.conn.execute(
            """
            INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (key, value, utcnow_iso()),
        )
        self.conn.commit()

    def as_dict(self) -> dict[str, str | None]:
        rows = self._fetchall("SELECT key, value FROM app_settings")
        return {row["key"]: row["value"] for row in rows}
