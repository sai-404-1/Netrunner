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
