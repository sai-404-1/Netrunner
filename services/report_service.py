from __future__ import annotations

import csv
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path


class ReportService:
    def __init__(self, db, reports_dir: str = "reports"):
        self.db = db
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def export_task_runs(self, fmt: str = "txt"):
        rows = self.db.task_runs.all(order_by="id DESC")
        items = [self._row_to_dict(row) for row in rows]

        timestamp = self._timestamp()
        filename = f"task_runs_{timestamp}.{fmt}"
        path = self.reports_dir / filename

        if fmt == "txt":
            self._write_task_runs_txt(path, items)
        elif fmt == "csv":
            self._write_csv(path, items)
        elif fmt == "json":
            self._write_json(path, items)
        else:
            raise ValueError(f"Unsupported report format: {fmt}")

        report = self.db.reports.create(
            name=f"Отчёт по задачам {timestamp}",
            report_type="tasks",
            format=fmt,
            source_type="global",
            source_id=None,
            file_path=str(path),
            summary_json=json.dumps(
                {
                    "rows": len(items),
                    "generated_at": self._iso_now(),
                },
                ensure_ascii=False,
            ),
            created_by_task_run_id=None,
        )
        return report, path

    def export_inventory(self, fmt: str = "txt"):
        rows = self.db.inventory.all(order_by="collected_at DESC")
        items = [self._row_to_dict(row) for row in rows]

        timestamp = self._timestamp()
        filename = f"inventory_{timestamp}.{fmt}"
        path = self.reports_dir / filename

        if fmt == "txt":
            self._write_inventory_txt(path, items)
        elif fmt == "csv":
            self._write_csv(path, items)
        elif fmt == "json":
            self._write_json(path, items)
        else:
            raise ValueError(f"Unsupported report format: {fmt}")

        report = self.db.reports.create(
            name=f"Отчёт по инвентаризации {timestamp}",
            report_type="inventory",
            format=fmt,
            source_type="global",
            source_id=None,
            file_path=str(path),
            summary_json=json.dumps(
                {
                    "rows": len(items),
                    "generated_at": self._iso_now(),
                },
                ensure_ascii=False,
            ),
            created_by_task_run_id=None,
        )
        return report, path

    def _write_task_runs_txt(self, path: Path, items: list[dict]):
        lines = ["=== ОТЧЁТ ПО ЗАДАЧАМ ===", ""]
        if not items:
            lines.append("Запусков пока нет.")
        else:
            for item in items:
                lines.append(
                    f"[{item.get('id')}] "
                    f"module_id={item.get('module_id')} | "
                    f"target={item.get('target_type')}:{item.get('target_id')} | "
                    f"status={item.get('status')} | "
                    f"trigger={item.get('trigger_type')} | "
                    f"started={item.get('started_at')} | "
                    f"finished={item.get('finished_at')}"
                )
                stdout_text = (item.get("stdout_text") or "").strip()
                stderr_text = (item.get("stderr_text") or "").strip()

                if stdout_text:
                    lines.append("--- stdout ---")
                    lines.append(stdout_text)

                if stderr_text:
                    lines.append("--- stderr ---")
                    lines.append(stderr_text)

                lines.append("-" * 80)

        path.write_text("\n".join(lines), encoding="utf-8")

    def _write_inventory_txt(self, path: Path, items: list[dict]):
        lines = ["=== ОТЧЁТ ПО ИНВЕНТАРИЗАЦИИ ===", ""]
        if not items:
            lines.append("Снимков инвентаризации пока нет.")
        else:
            for item in items:
                lines.append(
                    f"[{item.get('id')}] "
                    f"host_id={item.get('host_id')} | "
                    f"hostname={item.get('hostname')} | "
                    f"os={item.get('os_name')} | "
                    f"kernel={item.get('kernel')} | "
                    f"ram={item.get('ram_mb')} MB | "
                    f"free={item.get('disks_free_gb')} GB | "
                    f"at={item.get('collected_at')}"
                )

        path.write_text("\n".join(lines), encoding="utf-8")

    def _write_csv(self, path: Path, items: list[dict]):
        if not items:
            path.write_text("", encoding="utf-8")
            return

        fieldnames = list(items[0].keys())
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(items)

    def _write_json(self, path: Path, items: list[dict]):
        path.write_text(json.dumps(items, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    def export_host_status(self, fmt: str = "txt"):
        hosts = self.db.hosts.all(order_by="name")
        items = [self._row_to_dict(row) for row in hosts]
        active = sum(1 for h in items if h.get("is_active"))
        inactive = len(items) - active

        timestamp = self._timestamp()
        filename = f"host_status_{timestamp}.{fmt}"
        path = self.reports_dir / filename

        if fmt == "txt":
            self._write_host_status_txt(path, items, active, inactive)
        elif fmt == "csv":
            self._write_csv(path, items)
        elif fmt == "json":
            self._write_json(path, items)
        else:
            raise ValueError(f"Unsupported report format: {fmt}")

        report = self.db.reports.create(
            name=f"Отчёт по доступности хостов {timestamp}",
            report_type="host_status",
            format=fmt,
            source_type="global",
            source_id=None,
            file_path=str(path),
            summary_json=json.dumps(
                {
                    "total": len(items),
                    "active": active,
                    "inactive": inactive,
                    "generated_at": self._iso_now(),
                },
                ensure_ascii=False,
            ),
            created_by_task_run_id=None,
        )
        return report, path

    def _write_host_status_txt(self, path: Path, items: list[dict], active: int, inactive: int):
        lines = ["=== ОТЧЁТ ПО ДОСТУПНОСТИ ХОСТОВ ===", ""]
        lines.append(f"Всего хостов: {len(items)}")
        lines.append(f"Доступно: {active}")
        lines.append(f"Недоступно: {inactive}")
        lines.append("")
        if not items:
            lines.append("Хостов пока нет.")
        else:
            for item in items:
                status = "доступен" if item.get("is_active") else "недоступен"
                last_seen = item.get("last_seen_at") or "—"
                lines.append(
                    f"[{item.get('id')}] {item.get('name')} ({item.get('username')}@{item.get('address')}:{item.get('port')}) — {status}, последний раз: {last_seen}"
                )
        path.write_text("\n".join(lines), encoding="utf-8")

    def export_filesystem(self, fmt: str = "txt"):
        rows = self.db.inventory.latest_per_host()
        items = [self._row_to_dict(row) for row in rows]

        timestamp = self._timestamp()
        filename = f"filesystem_{timestamp}.{fmt}"
        path = self.reports_dir / filename

        if fmt == "txt":
            self._write_filesystem_txt(path, items)
        elif fmt == "csv":
            self._write_csv(path, items)
        elif fmt == "json":
            self._write_json(path, items)
        else:
            raise ValueError(f"Unsupported report format: {fmt}")

        report = self.db.reports.create(
            name=f"Отчёт по файловым системам {timestamp}",
            report_type="filesystem",
            format=fmt,
            source_type="global",
            source_id=None,
            file_path=str(path),
            summary_json=json.dumps(
                {
                    "hosts": len(items),
                    "generated_at": self._iso_now(),
                },
                ensure_ascii=False,
            ),
            created_by_task_run_id=None,
        )
        return report, path

    def _write_filesystem_txt(self, path: Path, items: list[dict]):
        lines = ["=== ОТЧЁТ ПО ФАЙЛОВЫМ СИСТЕМАМ ===", ""]
        if not items:
            lines.append("Данных инвентаризации пока нет.")
        else:
            for item in items:
                host_id = item.get("host_id")
                host = self.db.hosts.get(host_id)
                host_name = host.name if host else f"host_{host_id}"
                total = item.get("disks_total_gb") or 0
                free = item.get("disks_free_gb") or 0
                used = round(total - free, 2) if total else 0
                lines.append(f"[{host_id}] {host_name}")
                lines.append(f"  Всего диск: {total} GB | Свободно: {free} GB | Использовано: {used} GB")
                lines.append(f"  RAM: {item.get('ram_mb') or '—'} MB | OS: {item.get('os_name') or '—'}")
                lines.append("-" * 80)
        path.write_text("\n".join(lines), encoding="utf-8")

    def export_task_history(self, fmt: str = "txt"):
        rows = self.db.task_runs.all(order_by="id DESC")
        items = [self._row_to_dict(row) for row in rows]
        by_status = {}
        by_module = {}
        for item in items:
            status = item.get("status") or "unknown"
            by_status[status] = by_status.get(status, 0) + 1
            module_id = item.get("module_id")
            by_module[module_id] = by_module.get(module_id, 0) + 1

        timestamp = self._timestamp()
        filename = f"task_history_{timestamp}.{fmt}"
        path = self.reports_dir / filename

        if fmt == "txt":
            self._write_task_history_txt(path, items, by_status, by_module)
        elif fmt == "csv":
            self._write_csv(path, items)
        elif fmt == "json":
            self._write_json(path, items)
        else:
            raise ValueError(f"Unsupported report format: {fmt}")

        report = self.db.reports.create(
            name=f"Сводный отчёт по задачам {timestamp}",
            report_type="task_history",
            format=fmt,
            source_type="global",
            source_id=None,
            file_path=str(path),
            summary_json=json.dumps(
                {
                    "total": len(items),
                    "by_status": by_status,
                    "generated_at": self._iso_now(),
                },
                ensure_ascii=False,
            ),
            created_by_task_run_id=None,
        )
        return report, path

    def _write_task_history_txt(self, path: Path, items: list[dict], by_status: dict, by_module: dict):
        lines = ["=== СВОДНЫЙ ОТЧЁТ ПО ЗАДАЧАМ ===", ""]
        lines.append(f"Всего запусков: {len(items)}")
        if by_status:
            lines.append("По статусам: " + ", ".join(f"{k}={v}" for k, v in by_status.items()))
        lines.append("")
        if not items:
            lines.append("Запусков пока нет.")
        else:
            for item in items:
                lines.append(
                    f"[{item.get('id')}] module_id={item.get('module_id')} | "
                    f"target={item.get('target_type')}:{item.get('target_id')} | "
                    f"status={item.get('status')} | started={item.get('started_at')}"
                )
                lines.append("-" * 80)
        path.write_text("\n".join(lines), encoding="utf-8")

    def export_from_task_run(self, task_run_id: int, fmt: str = "txt"):
        task_run = self.db.task_runs.get(task_run_id)
        if not task_run:
            raise ValueError(f"Task run #{task_run_id} not found")

        per_host = []
        if task_run.per_host_json:
            try:
                per_host = json.loads(task_run.per_host_json)
            except Exception:
                per_host = []
        if not per_host:
            per_host = [
                {
                    "host_id": task_run.target_id,
                    "name": f"target_{task_run.target_id}",
                    "address": "",
                    "port": 22,
                    "username": "",
                    "output": task_run.stdout_text or "",
                    "stderr": task_run.stderr_text or "",
                }
            ]

        for item in per_host:
            item.setdefault("stderr", task_run.stderr_text or "")

        module = self.db.modules.get(task_run.module_id)
        module_name = module.name if module else f"module_{task_run.module_id}"
        timestamp = self._timestamp()
        filename = f"task_run_{task_run_id}_{timestamp}.{fmt}"
        path = self.reports_dir / filename

        if fmt == "txt":
            self._write_task_run_txt(path, task_run, per_host, module_name)
        elif fmt == "csv":
            self._write_task_run_csv(path, per_host)
        elif fmt == "json":
            self._write_task_run_json(path, per_host, task_run, module_name)
        else:
            raise ValueError(f"Unsupported report format: {fmt}")

        report = self.db.reports.create(
            name=f"Отчёт по задаче #{task_run_id} {timestamp}",
            report_type="task_run",
            format=fmt,
            source_type="task_run",
            source_id=task_run_id,
            file_path=str(path),
            summary_json=json.dumps(
                {
                    "task_run_id": task_run_id,
                    "module_name": module_name,
                    "hosts": len(per_host),
                    "status": task_run.status,
                    "generated_at": self._iso_now(),
                },
                ensure_ascii=False,
            ),
            created_by_task_run_id=task_run_id,
        )
        return report, path

    def _write_task_run_txt(self, path: Path, task_run, per_host: list[dict], module_name: str):
        lines = [f"=== ОТЧЁТ ПО ЗАДАЧЕ #{task_run.id} ===", ""]
        lines.append(f"Модуль: {module_name}")
        lines.append(f"Статус: {task_run.status}")
        lines.append(f"Цель: {task_run.target_type}:{task_run.target_id}")
        lines.append(f"Запущено: {task_run.started_at}")
        lines.append(f"Завершено: {task_run.finished_at or '—'}")
        lines.append("")
        if not per_host:
            lines.append("Нет данных по хостам.")
        else:
            for item in per_host:
                lines.append(f"--- {item.get('name')} ({item.get('username')}@{item.get('address')}:{item.get('port')}) ---")
                output = (item.get("output") or "").strip()
                stderr = (item.get("stderr") or "").strip()
                if output:
                    lines.append(output)
                if stderr:
                    lines.append("— stderr —")
                    lines.append(stderr)
                lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")

    def _write_task_run_csv(self, path: Path, per_host: list[dict]):
        if not per_host:
            path.write_text("", encoding="utf-8")
            return
        fieldnames = ["name", "address", "port", "username", "output", "stderr"]
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(per_host)

    def _write_task_run_json(self, path: Path, per_host: list[dict], task_run, module_name: str):
        payload = {
            "task_run_id": task_run.id,
            "module": module_name,
            "status": task_run.status,
            "target_type": task_run.target_type,
            "target_id": task_run.target_id,
            "started_at": task_run.started_at,
            "finished_at": task_run.finished_at,
            "hosts": per_host,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    def _row_to_dict(self, row):
        if row is None:
            return {}

        if is_dataclass(row):
            return asdict(row)

        if hasattr(row, "__dict__"):
            return dict(row.__dict__)

        return dict(row)

    def _timestamp(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    def _iso_now(self) -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
