# database/repos

Репозитории — слой доступа к данным. По одному репозиторию на таблицу; все наследуют
`BaseRepository` и возвращают модели из `database/models/`. Доступны через фасад
`Database` как атрибуты (`db.hosts`, `db.users`, …).

## Базовый класс

### `base.py`
- `utcnow_iso()` — текущее UTC-время в ISO-формате (для `created_at`/`updated_at`).
- `_safe_ident(name)` — валидация SQL-идентификатора/порядка сортировки (защита от инъекций).
- `class BaseRepository` — общий CRUD:
  - `all(order_by)`, `get(item_id)`, `filter(**f)`, `get_one_by(**f)`, `exists(**f)`,
    `create(**data)`, `update(item_id, **data)`, `delete(item_id)`;
  - служебные `_row_to_model`, `_fetchone`, `_fetchall`.

## Репозитории

- `host_repo.py` — `HostRepo`: `create`, `update`, `by_group(group_id)`, `touch_seen(host_id)`.
- `ssh_key_repo.py` — `SSHKeyRepo`: `create`, `set_default(key_id)`, `default()`.
- `group_repo.py` — `GroupRepo`: `create`, `add_host`, `remove_host`, `hosts(group_id)`,
  `first_group_id_for_host`, `first_group_for_host`.
- `module_repo.py` — `ModuleRepo`: `create`, `enabled()`, `builtin()`, `by_slug(slug)`.
- `task_template_repo.py` — `TaskTemplateRepo`: `create`.
- `task_run_repo.py` — `TaskRunRepo`: `create`, `start(...)`, `finish(...)`,
  `list_recent(limit)`, `clear_all()`.
- `schedule_repo.py` — `ScheduledTaskRepo`: `create`, `due(before_iso)`, `mark_ran(task_id, when)`.
- `inventory_repo.py` — `InventoryRepo`: `create`, `latest_for_host`, `history_for_host`,
  `latest_per_host()`.
- `report_repo.py` — `ReportRepo`: `create`, `latest(limit, report_type)`, `clear_all()`.
- `user_repo.py` — `UserRepo`: `create`, `update`, `by_username(username)`.
- `user_group_access_repo.py` — `UserGroupAccessRepo`: `by_user`, `has_access`,
  `set_access`, `clear_user`.
- `user_module_access_repo.py` — `UserModuleAccessRepo`: `by_user`, `by_user_module`,
  `set_access`, `clear_user`.
- `board_repo.py` — `BoardRepo`: `by_owner`, `all_boards`, `create_board`,
  `get_with_hosts(board_id)`, `save_layout(board_id, positions)`.
