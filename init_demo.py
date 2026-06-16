#!/usr/bin/env python3
"""
NetRunner — Init Demo Data
Создаёт базу данных и заполняет её тестовыми данными для демонстрации.
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

    print("[init] Создание демо-данных...")

    key_path = "keys/id_ed25519" if not docker else "/app/keys/id_ed25519"
    pub_path = "keys/id_ed25519.pub" if not docker else "/app/keys/id_ed25519.pub"

    # 1. SSH key
    key = db.ssh_keys.create(
        name="default_key",
        private_key_path=key_path,
        public_key_path=pub_path,
        has_passphrase=0,
        is_default=1,
    )
    print(f"[init] SSH key: id={key.id}")

    # 2. Hosts
    if docker:
        hosts_data = [
            ("host-1", "netrunner-host-1", 22, "admin", "Web-сервер Alpine 3.20 (Docker)"),
            ("host-2", "netrunner-host-2", 22, "admin", "База данных Alpine 3.20 (Docker)"),
            ("host-3", "netrunner-host-3", 22, "admin", "Прикладной сервер Alpine 3.20 (Docker)"),
        ]
    else:
        hosts_data = [
            ("host-1", "localhost", 2221, "admin", "Web-сервер Alpine 3.20"),
            ("host-2", "localhost", 2222, "admin", "База данных Alpine 3.20"),
            ("host-3", "localhost", 2223, "admin", "Прикладной сервер Alpine 3.20"),
        ]
    host_ids = []
    for name, address, port, username, desc in hosts_data:
        h = db.hosts.create(
            name=name,
            address=address,
            port=port,
            username=username,
            ssh_key_id=key.id,
            description=desc,
            is_active=1,
        )
        host_ids.append(h.id)
        print(f"[init] Host {name}: id={h.id}")

    # 3. Group
    group = db.groups.create(
        name="test-group",
        kind="custom",
        description="Тестовая группа для демонстрации",
    )
    print(f"[init] Group test-group: id={group.id}")

    # 4. Add hosts to group
    for hid in host_ids:
        db.groups.add_host(group.id, hid)
    print(f"[init] {len(host_ids)} hosts added to group")

    # 5. Modules (bootstrap)
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

    # 6. Task templates
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

    # 7. Task runs history
    task_runs = [
        (1, "host", host_ids[0], "success", "Host host-1 is reachable", "", 0),
        (2, "host", host_ids[1], "success", "Host host-2 is reachable", "", 0),
        (3, "host", host_ids[2], "error", "", "Connection timeout", 1),
        (1, "group", group.id, "success", "Group check completed", "", 0),
    ]
    for mod_id, target_type, target_id, status, stdout, stderr, code in task_runs:
        db.task_runs.create(
            module_id=mod_id,
            target_type=target_type,
            target_id=target_id,
            status=status,
            stdout_text=stdout,
            stderr_text=stderr,
            exit_code=code,
            trigger_type="manual",
        )
    print("[init] 4 task runs added")

    # 8. Inventory snapshots
    inv_data = [
        (host_ids[0], "host-1", "Alpine Linux", "6.6.0-1", 3600, 2048, 16.0, 10.0, 2),
        (host_ids[1], "host-2", "Alpine Linux", "6.6.0-1", 7200, 1024, 8.0, 5.0, 1),
        (host_ids[2], "host-3", "Alpine Linux", "6.6.0-1", 1800, 512, 4.0, 2.0, 1),
    ]
    for hid, hostname, os_name, kernel, uptime, ram, disk_total, disk_free, disk_count in inv_data:
        db.inventory.create(
            host_id=hid,
            hostname=hostname,
            os_name=os_name,
            kernel=kernel,
            uptime_seconds=uptime,
            ram_mb=ram,
            disks_total_gb=disk_total,
            disks_free_gb=disk_free,
            disks_count=disk_count,
            raw_json=json.dumps({"demo": True}, ensure_ascii=False),
        )
    print("[init] 3 inventory snapshots added")

    # 9. Scheduled tasks
    db.scheduled.create(
        name="Ежедневная проверка",
        template_id=1,
        target_type="group",
        target_id=group.id,
        run_at="2026-06-13T06:00:00+00:00",
        is_enabled=1,
    )
    print("[init] 1 scheduled task added")

    # 10. Reports
    db.reports.create(
        name="Демо-отчёт задач",
        report_type="tasks",
        format="txt",
        source_type="task_runs",
        file_path="/app/reports/demo_tasks.txt",
    )
    print("[init] 1 report added")

    db.commit()
    db.close()
    print("[init] Готово! База заполнена.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Инициализация демо-данных NetRunner")
    parser.add_argument("--db", default="data/netrunner.db", help="Путь к базе данных")
    parser.add_argument("--docker", action="store_true", help="Режим Docker: хосты на localhost:порт")
    args = parser.parse_args()
    init_demo_data(db_path=args.db, docker=args.docker)
