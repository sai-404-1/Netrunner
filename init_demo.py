#!/usr/bin/env python3
"""
NetRunner — Init Demo Data
Создаёт базу данных и заполняет её начальными данными.
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from database import open_database


def now():
    return datetime.now(timezone.utc).isoformat()


def init_demo_data(db_path: str = "data/netrunner.db", docker: bool = False):
    db = open_database(db_path)

    print("[init] Инициализация базы данных...")

    key_path = "keys/id_ed25519" if not docker else "/app/keys/id_ed25519"
    pub_path = "keys/id_ed25519.pub" if not docker else "/app/keys/id_ed25519.pub"

    # 1. Default SSH key
    key = db.ssh_keys.create(
        name="default_key",
        private_key_path=key_path,
        public_key_path=pub_path,
        has_passphrase=0,
        is_default=1,
    )
    print(f"[init] SSH key: id={key.id}")

    # 2. Default group
    group = db.groups.create(
        name="all-hosts",
        kind="custom",
        description="Все хосты",
    )
    print(f"[init] Group all-hosts: id={group.id}")

    # 3. Builtin modules
    modules = [
        ("availability_check", "computer.module.availability_check", "AvailabilityCheck"),
        ("inventory_collect", "computer.module.inventory_collect", "InventoryCollect"),
        ("mass_ssh", "computer.module.executor_ssh", "SSHExecutor"),
    ]
    for slug, path, cls in modules:
        db.modules.create(
            name=slug,
            slug=slug,
            module_path=path,
            class_name=cls,
            is_builtin=1,
            is_enabled=1,
        )
    print("[init] 3 builtin modules registered")

    # 4. Task templates
    for name, slug in [("Проверка доступности", "availability_check"),
                       ("Сбор инвентаризации", "inventory_collect")]:
        mod = db.modules.by_slug(slug)
        if mod:
            db.task_templates.create(
                name=name,
                module_id=mod.id,
                default_args_json=json.dumps({}, ensure_ascii=False),
            )
    print("[init] 2 task templates created")

    db.commit()
    db.close()
    print("[init] Готово! База инициализирована.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Инициализация NetRunner")
    parser.add_argument("--db", default="data/netrunner.db", help="Путь к базе данных")
    parser.add_argument("--docker", action="store_true", help="Режим Docker")
    args = parser.parse_args()
    init_demo_data(db_path=args.db, docker=args.docker)
