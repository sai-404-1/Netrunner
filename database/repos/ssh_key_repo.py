from __future__ import annotations

from .base import BaseRepository, utcnow_iso
from ..models.ssh_key import SSHKey


class SSHKeyRepo(BaseRepository):
    model_cls = SSHKey

    def create(self, **data):
        data.setdefault('created_at', utcnow_iso())
        if data.get('is_default'):
            self.conn.execute('UPDATE ssh_keys SET is_default = 0')
        return super().create(**data)

    def set_default(self, key_id: int):
        self.conn.execute('UPDATE ssh_keys SET is_default = 0')
        self.conn.execute('UPDATE ssh_keys SET is_default = 1 WHERE id = ?', (key_id,))
        self.conn.commit()
        return self.get(key_id)

    def default(self):
        return self.get_one_by(is_default=1)
