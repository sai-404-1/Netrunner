from __future__ import annotations

from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import Iterable, Sequence
import shutil


MIN_WIDTH = 90
MAX_WIDTH = 120
COLUMN_GAP = "  "


def ui_width() -> int:
    """Единая рабочая ширина TUI.

    Берётся из текущего терминала, но ограничивается сверху, чтобы
    интерфейс не становился слишком широким для скриншотов в дипломе.
    """
    columns = shutil.get_terminal_size((120, 30)).columns
    return min(max(MIN_WIDTH, columns - 2), MAX_WIDTH)


def section(title: str):
    width = ui_width()
    print("\n" + "=" * width)
    print(str(title).center(width))
    print("=" * width)


def subsection(title: str):
    width = min(ui_width(), max(24, len(str(title)) + 4))
    print("\n" + str(title))
    print("-" * width)


def info(label: str, value):
    width = ui_width()
    label_width = 24
    value_width = max(10, width - label_width - 3)
    print(f"{label:<{label_width}}: {shorten(format_value(value), value_width)}")


def yes_no(value) -> str:
    return "Да" if bool(value) else "Нет"


def format_value(value):
    if value is None or value == "":
        return "—"
    return str(value)


def format_dt(value, seconds: bool = True) -> str:
    """Короткий формат даты для табличного вывода."""
    if not value:
        return "—"

    text = str(value).strip()
    try:
        normalized = text.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        return dt.strftime("%d.%m.%Y %H:%M:%S" if seconds else "%d.%m.%Y %H:%M")
    except Exception:
        # Если значение пришло не в ISO-формате, просто аккуратно режем строку.
        return shorten(text, 19 if seconds else 16)


def shorten(text, limit: int = 100) -> str:
    value = "" if text is None else str(text)
    value = value.replace("\r", "").replace("\n", " ").strip()
    if len(value) <= limit:
        return value
    if limit <= 3:
        return value[:limit]
    return value[: limit - 3] + "..."


def status_ru(status: str | None) -> str:
    mapping = {
        "success": "успешно",
        "error": "ошибка",
        "running": "выполняется",
        "pending": "ожидает",
        "manual": "ручной запуск",
        "scheduled": "по расписанию",
    }
    return mapping.get(status or "", status or "—")


def _normalise_width_specs(headers: Sequence[str], rows: list[list[str]], specs: Sequence[int | None] | None) -> list[int]:
    """Рассчитывает ширины колонок под текущую ширину терминала.

    Если в specs указан None, колонка считается гибкой и получает остаток
    свободного места. Это решает проблему, когда последняя колонка
    обрезалась, хотя справа ещё оставалось место.
    """
    n = len(headers)
    available = ui_width() - len(COLUMN_GAP) * (n - 1)
    available = max(n, available)

    natural = [len(str(header)) for header in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            natural[idx] = max(natural[idx], len(str(cell)))

    if not specs:
        specs = [None if idx == n - 1 else min(natural[idx], 24) for idx in range(n)]

    specs = list(specs)
    fixed_indices = [idx for idx, spec in enumerate(specs) if isinstance(spec, int)]
    flex_indices = [idx for idx, spec in enumerate(specs) if spec is None]

    widths = [0] * n
    for idx in fixed_indices:
        widths[idx] = max(len(str(headers[idx])), int(specs[idx]))

    fixed_total = sum(widths)
    remaining = available - fixed_total

    if flex_indices:
        min_flex = [max(len(str(headers[idx])), min(natural[idx], 12)) for idx in flex_indices]
        min_total = sum(min_flex)

        if remaining >= min_total:
            # Сначала даём каждой гибкой колонке естественный минимум,
            # остаток отдаём последней гибкой колонке. Обычно это описание.
            for idx, min_width in zip(flex_indices, min_flex):
                widths[idx] = min_width
            widths[flex_indices[-1]] += remaining - min_total
        else:
            # Места мало: делим остаток между гибкими колонками поровну.
            share = max(4, remaining // len(flex_indices))
            for idx in flex_indices:
                widths[idx] = max(len(str(headers[idx])), share)
    else:
        widths = [min(widths[idx], natural[idx]) for idx in range(n)]

    total = sum(widths)
    overflow = total - available
    if overflow > 0:
        # Уменьшаем самые широкие колонки, но не ломаем заголовки.
        shrinkable = sorted(range(n), key=lambda idx: widths[idx], reverse=True)
        for idx in shrinkable:
            min_width = max(len(str(headers[idx])), 4)
            can_shrink = widths[idx] - min_width
            if can_shrink <= 0:
                continue
            delta = min(can_shrink, overflow)
            widths[idx] -= delta
            overflow -= delta
            if overflow <= 0:
                break

    return widths


def print_table(headers: Sequence[str], rows: Iterable[Sequence[object]], max_widths: Sequence[int | None] | None = None):
    rows = [[format_value(cell) for cell in row] for row in rows]
    widths = _normalise_width_specs(headers, rows, max_widths)

    def render_row(row_values):
        cells = []
        for idx, value in enumerate(row_values):
            cells.append(shorten(value, widths[idx]).ljust(widths[idx]))
        return COLUMN_GAP.join(cells).rstrip()

    print(render_row([str(header) for header in headers]))
    print(COLUMN_GAP.join("-" * width for width in widths).rstrip())

    for row in rows:
        print(render_row(row))


@dataclass
class MenuAction:
    title: str

    def exec(self):
        raise NotImplementedError


class ShowHostsAction(MenuAction):
    def __init__(self, host_service):
        super().__init__(title="Хосты в базе")
        self.host_service = host_service

    def exec(self):
        hosts = self.host_service.all_hosts()
        section("ХОСТЫ В БАЗЕ")

        if not hosts:
            print("Хостов пока нет.")
            return

        rows = []
        for host in hosts:
            rows.append([
                host.id,
                host.name,
                f"{host.username}@{host.address}:{host.port}",
                yes_no(host.is_active),
                host.ssh_key_id or "—",
                host.description or "—",
            ])

        print_table(
            ["ID", "Имя", "Адрес", "Активен", "SSH key", "Описание"],
            rows,
            max_widths=[4, 26, 38, 8, 8, None],
        )


class ShowGroupsAction(MenuAction):
    def __init__(self, db):
        super().__init__(title="Группы в базе")
        self.db = db

    def exec(self):
        groups = self.db.groups.all()
        section("ГРУППЫ В БАЗЕ")

        if not groups:
            print("Групп пока нет.")
            return

        rows = []
        for group in groups:
            rows.append([
                group.id,
                group.name,
                group.kind,
                group.description or "—",
            ])

        print_table(
            ["ID", "Название", "Тип", "Описание"],
            rows,
            max_widths=[4, 28, 16, None],
        )


class ShowModulesAction(MenuAction):
    def __init__(self, db):
        super().__init__(title="Модули в базе")
        self.db = db

    def exec(self):
        modules = self.db.modules.all()
        section("МОДУЛИ В БАЗЕ")

        if not modules:
            print("Модулей пока нет.")
            return

        rows = []
        for module in modules:
            rows.append([
                module.id,
                module.name,
                module.slug,
                yes_no(module.is_builtin),
                yes_no(module.is_enabled),
                module.description or "—",
            ])

        print_table(
            ["ID", "Название", "Slug", "Системный", "Включён", "Описание"],
            rows,
            max_widths=[4, 26, 26, 10, 9, None],
        )


class ShowTaskHistoryAction(MenuAction):
    def __init__(self, db):
        super().__init__(title="История задач")
        self.db = db

    def exec(self):
        runs = self.db.task_runs.all(order_by="id DESC")
        section("ИСТОРИЯ ЗАДАЧ")

        if not runs:
            print("Запусков пока нет.")
            return

        rows = []
        for run in runs[:30]:
            module = self.db.modules.get(run.module_id) if run.module_id else None
            rows.append([
                run.id,
                module.slug if module else run.module_id,
                f"{run.target_type}:{run.target_id}",
                status_ru(run.status),
                status_ru(run.trigger_type),
                format_dt(run.started_at),
                format_dt(run.finished_at),
            ])

        print_table(
            ["ID", "Модуль", "Цель", "Статус", "Запуск", "Начало", "Конец"],
            rows,
            max_widths=[4, 22, 10, 10, 14, 19, 19],
        )


class ShowScheduledTasksAction(MenuAction):
    def __init__(self, db):
        super().__init__(title="Запланированные задачи")
        self.db = db

    def exec(self):
        tasks = self.db.scheduled.all()
        section("ЗАПЛАНИРОВАННЫЕ ЗАДАЧИ")

        if not tasks:
            print("Запланированных задач пока нет.")
            return

        rows = []
        for task in tasks:
            template = self.db.task_templates.get(task.template_id) if task.template_id else None
            rows.append([
                task.id,
                task.name,
                template.name if template else task.template_id,
                f"{task.target_type}:{task.target_id}",
                format_dt(task.run_at),
                yes_no(task.is_enabled),
                format_dt(task.last_run_at),
            ])

        print_table(
            ["ID", "Название", "Шаблон", "Цель", "Запуск", "Активна", "Последний запуск"],
            rows,
            max_widths=[4, 28, 22, 10, 19, 8, None],
        )


class ShowReportsAction(MenuAction):
    def __init__(self, db):
        super().__init__(title="Отчёты")
        self.db = db

    def exec(self):
        reports = self.db.reports.all()
        section("ОТЧЁТЫ")

        if not reports:
            print("Отчётов пока нет.")
            return

        rows = []
        for report in reports:
            rows.append([
                report.id,
                report.name,
                report.report_type,
                report.format,
                report.file_path,
                format_dt(report.created_at),
            ])

        print_table(
            ["ID", "Название", "Тип", "Формат", "Файл", "Создан"],
            rows,
            max_widths=[4, 28, 12, 8, None, 19],
        )


class RunRegisteredModuleAction(MenuAction):
    def __init__(self, db, task_runner, registry_item):
        super().__init__(title=registry_item.title)
        self.db = db
        self.task_runner = task_runner
        self.registry_item = registry_item

    def exec(self):
        # legacy-модули запускаем по-старому
        if not self.registry_item.supports_task_runner:
            return self.registry_item.instance.exec()

        target_type, target_id = self._pick_target()
        if not target_type:
            print("Цель не выбрана.")
            return

        args = {}
        if hasattr(self.registry_item.instance, "prompt_args"):
            maybe_args = self.registry_item.instance.prompt_args()
            if maybe_args is None:
                print("Отменено.")
                return
            args = maybe_args

        try:
            run = self.task_runner.run(
                module_slug=self.registry_item.slug,
                target_type=target_type,
                target_id=target_id,
                args=args,
                trigger_type="manual",
            )
        except Exception as exc:
            section("ОШИБКА ВЫПОЛНЕНИЯ ЗАДАЧИ")
            info("Модуль", self.registry_item.slug)
            info("Цель", f"{target_type}:{target_id}")
            info("Ошибка", exc)
            return

        section("РЕЗУЛЬТАТ ВЫПОЛНЕНИЯ ЗАДАЧИ")
        info("ID задачи", run.id)
        info("Модуль", self.registry_item.slug)
        info("Цель", f"{run.target_type}:{run.target_id}")
        info("Статус", status_ru(run.status))
        info("Начало", format_dt(run.started_at))
        info("Завершение", format_dt(run.finished_at))

        if getattr(run, "stdout_text", ""):
            subsection("STDOUT")
            print(run.stdout_text)

        if getattr(run, "stderr_text", ""):
            subsection("STDERR")
            print(run.stderr_text)

    def _pick_target(self):
        section("ВЫБОР ЦЕЛИ")
        print("1 — один хост")
        print("2 — группа хостов")
        mode = input("\nВыберите режим: ").strip()

        if mode == "1":
            hosts = self.db.hosts.all()
            if not hosts:
                print("Хостов пока нет.")
                return None, None

            rows = [[host.id, host.name, f"{host.username}@{host.address}:{host.port}"] for host in hosts]
            print_table(["ID", "Имя", "Адрес"], rows, max_widths=[5, 28, None])

            raw = input("\nВведите ID хоста: ").strip()
            if not raw.isdigit():
                return None, None
            return "host", int(raw)

        if mode == "2":
            groups = self.db.groups.all()
            if not groups:
                print("Групп пока нет.")
                return None, None

            rows = [[group.id, group.name, group.kind] for group in groups]
            print_table(["ID", "Название", "Тип"], rows, max_widths=[5, 34, None])

            raw = input("\nВведите ID группы: ").strip()
            if not raw.isdigit():
                return None, None
            return "group", int(raw)

        return None, None


class ShowInventorySnapshotsAction(MenuAction):
    def __init__(self, db):
        super().__init__(title="Инвентаризация")
        self.db = db

    def exec(self):
        snapshots = self.db.inventory.all(order_by="collected_at DESC")
        section("ИНВЕНТАРИЗАЦИЯ")

        if not snapshots:
            print("Снимков инвентаризации пока нет.")
            return

        rows = []
        for snap in snapshots[:30]:
            rows.append([
                snap.id,
                snap.host_id,
                snap.hostname or "—",
                snap.os_name or "—",
                snap.kernel or "—",
                f"{snap.ram_mb or 0} MB",
                f"{snap.disks_free_gb or 0} GB",
                format_dt(snap.collected_at),
            ])

        print_table(
            ["ID", "Host", "Hostname", "ОС", "Ядро", "RAM", "Свободно", "Собрано"],
            rows,
            max_widths=[4, 6, 18, 18, None, 10, 10, 19],
        )


class ShowTaskTemplatesAction(MenuAction):
    def __init__(self, db):
        super().__init__(title="Шаблоны задач")
        self.db = db

    def exec(self):
        templates = self.db.task_templates.all()
        section("ШАБЛОНЫ ЗАДАЧ")

        if not templates:
            print("Шаблонов пока нет.")
            return

        rows = []
        for template in templates:
            module_row = self.db.modules.get(template.module_id)
            module_slug = module_row.slug if module_row else "unknown"
            rows.append([
                template.id,
                template.name,
                module_slug,
                template.description or "—",
            ])

        print_table(
            ["ID", "Название", "Модуль", "Описание"],
            rows,
            max_widths=[5, 30, 26, None],
        )


class CreateScheduledTaskAction(MenuAction):
    def __init__(self, db):
        super().__init__(title="Создать запланированную задачу")
        self.db = db

    def exec(self):
        templates = self.db.task_templates.all()
        section("СОЗДАНИЕ ЗАПЛАНИРОВАННОЙ ЗАДАЧИ")

        if not templates:
            print("Шаблонов задач пока нет.")
            return

        rows = []
        for template in templates:
            module_row = self.db.modules.get(template.module_id)
            module_slug = module_row.slug if module_row else "unknown"
            rows.append([template.id, template.name, module_slug])

        print_table(["ID", "Шаблон", "Модуль"], rows, max_widths=[5, 34, None])

        raw_template_id = input("\nВведите ID шаблона: ").strip()
        if not raw_template_id.isdigit():
            print("Некорректный ID шаблона.")
            return
        template_id = int(raw_template_id)

        print("\nЦель выполнения:")
        print("1 — один хост")
        print("2 — группа хостов")
        mode = input("\nВыберите режим: ").strip()

        if mode == "1":
            hosts = self.db.hosts.all()
            if not hosts:
                print("Хостов пока нет.")
                return

            rows = [[host.id, host.name, f"{host.username}@{host.address}:{host.port}"] for host in hosts]
            print_table(["ID", "Имя", "Адрес"], rows, max_widths=[5, 28, None])

            raw_target_id = input("\nВведите ID хоста: ").strip()
            if not raw_target_id.isdigit():
                print("Некорректный ID хоста.")
                return

            target_type = "host"
            target_id = int(raw_target_id)

        elif mode == "2":
            groups = self.db.groups.all()
            if not groups:
                print("Групп пока нет.")
                return

            rows = [[group.id, group.name, group.kind] for group in groups]
            print_table(["ID", "Название", "Тип"], rows, max_widths=[5, 34, None])

            raw_target_id = input("\nВведите ID группы: ").strip()
            if not raw_target_id.isdigit():
                print("Некорректный ID группы.")
                return

            target_type = "group"
            target_id = int(raw_target_id)
        else:
            print("Некорректный режим.")
            return

        print(
            "\nВремя запуска:\n"
            " - число означает запуск через N секунд;\n"
            " - дата вводится в формате YYYY-MM-DD HH:MM."
        )
        raw_time = input("Введите время запуска: ").strip()

        run_at = self._parse_run_at(raw_time)
        if not run_at:
            print("Не удалось разобрать время запуска.")
            return

        template = self.db.task_templates.get(template_id)
        if not template:
            print("Шаблон не найден.")
            return

        name = f"{template.name} @ {run_at}"

        scheduled = self.db.scheduled.create(
            name=name,
            template_id=template_id,
            target_type=target_type,
            target_id=target_id,
            run_at=run_at,
            is_enabled=1,
        )

        section("ЗАПЛАНИРОВАННАЯ ЗАДАЧА СОЗДАНА")
        info("ID", scheduled.id)
        info("Название", scheduled.name)
        info("Цель", f"{scheduled.target_type}:{scheduled.target_id}")
        info("Время запуска", format_dt(scheduled.run_at))

    def _parse_run_at(self, raw: str) -> str | None:
        raw = raw.strip()
        if not raw:
            return None

        if raw.isdigit():
            dt = datetime.now(timezone.utc) + timedelta(seconds=int(raw))
            return dt.replace(microsecond=0).isoformat()

        # ISO 8601 with explicit timezone offset (e.g. from the server UI: "2026-06-15T12:00:00+03:00")
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()
        except (ValueError, AttributeError):
            pass

        # Plain "YYYY-MM-DD HH:MM" entered in the TUI — treat as local time
        try:
            dt_local = datetime.strptime(raw, "%Y-%m-%d %H:%M")
            dt_utc = dt_local.astimezone(timezone.utc)
            return dt_utc.replace(microsecond=0).isoformat()
        except Exception:
            return None


class RunSchedulerTickAction(MenuAction):
    def __init__(self, scheduler):
        super().__init__(title="Прогнать планировщик")
        self.scheduler = scheduler

    def exec(self):
        section("ПЛАНИРОВЩИК")
        self.scheduler.tick()
        print("Проверка расписания выполнена.")


class ExportTaskRunsReportAction(MenuAction):
    def __init__(self, report_service):
        super().__init__(title="Экспорт отчёта по задачам")
        self.report_service = report_service

    def exec(self):
        fmt = self._ask_format()
        if not fmt:
            print("Отменено.")
            return

        report, path = self.report_service.export_task_runs(fmt=fmt)
        section("ОТЧЁТ СОЗДАН")
        info("ID", report.id)
        info("Название", report.name)
        info("Путь", path)

    def _ask_format(self):
        raw = input("Формат отчёта (txt/csv/json): ").strip().lower()
        if raw in {"txt", "csv", "json"}:
            return raw
        return None


class ExportInventoryReportAction(MenuAction):
    def __init__(self, report_service):
        super().__init__(title="Экспорт отчёта по инвентаризации")
        self.report_service = report_service

    def exec(self):
        fmt = self._ask_format()
        if not fmt:
            print("Отменено.")
            return

        report, path = self.report_service.export_inventory(fmt=fmt)
        section("ОТЧЁТ СОЗДАН")
        info("ID", report.id)
        info("Название", report.name)
        info("Путь", path)

    def _ask_format(self):
        raw = input("Формат отчёта (txt/csv/json): ").strip().lower()
        if raw in {"txt", "csv", "json"}:
            return raw
        return None
