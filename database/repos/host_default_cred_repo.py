from database.models.host_default_cred import HostDefaultCredentials
from database.repos import BaseRepository, utcnow_iso


class HostDefaultCredRepo(BaseRepository):
    model_cls = HostDefaultCredentials
    table_name = 'host_default_credentials'

    def create(self, **data):
        now = utcnow_iso()
        data.setdefault('last_updated_at', now)
        return super().create(**data)

    def update(self, item_id: int, **data):
        data['last_updated_at'] = utcnow_iso()
        return super().update(item_id, **data)

    def get_default(self):
        """Единственная запись стандартных кредов (первая по id) или None."""
        row = self._fetchone(f'SELECT * FROM {self.table_name} ORDER BY id LIMIT 1')
        return self._row_to_model(row)

    def upsert(self, username: str, password_encrypted: str):
        """Создать или обновить единственную запись стандартных кредов.

        Таблица рассчитана на одну строку: если запись уже есть — обновляем
        её, иначе создаём новую. Возвращает сохранённую модель.
        """
        existing = self.get_default()
        if existing is None:
            return self.create(
                username=username,
                password_encrypted=password_encrypted,
            )
        return self.update(
            existing.id,
            username=username,
            password_encrypted=password_encrypted,
        )

    def update_username(self, username: str):
        """Обновить только имя пользователя в стандартных кредах."""
        existing = self.get_default()
        if existing is None:
            return None
        return self.update(existing.id, username=username)

    def update_password(self, password_encrypted: str):
        """Обновить только (зашифрованный) пароль в стандартных кредах."""
        existing = self.get_default()
        if existing is None:
            return None
        return self.update(existing.id, password_encrypted=password_encrypted)
