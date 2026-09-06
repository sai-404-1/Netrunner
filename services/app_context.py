from __future__ import annotations

import importlib.util
import json

# TODO не забыть проверить и стереть это перед коммитом
# import logging
from .logger import Logger

import sys
from dataclasses import dataclass
from pathlib import Path

import computer.module as builtin_modules
import computer.users_module as user_modules_pkg

from database import open_database
from services import HostService, ModuleRegistry, TaskRunner, Scheduler
from services.auth_service import AuthService
from services.execution_settings import ExecutionSettings
from services.report_service import ReportService
from services.history import HistoryService
from services.scenario_runner import ScenarioRunner


# logger = logging.getLogger("netrunner")
logger = Logger()

@dataclass(slots=True)
class AppContext:
    """Общий контекст приложения NetRunner.

    Контекст собирает базу данных, сервисы, реестр модулей, исполнитель задач,
    планировщик и сервис отчётов. Его используют как консольный интерфейс, так и
    веб-панель, чтобы оба способа входа работали с одной логикой системы.
    """

    db: object
    host_service: HostService
    module_registry: ModuleRegistry
    task_runner: TaskRunner
    scheduler: Scheduler
    auth_service: AuthService
    report_service: ReportService
    scenario_runner: ScenarioRunner
    history: HistoryService
    execution_settings: ExecutionSettings
    db_path: str
    reports_dir: str

    def close(self) -> None:
        self.db.close()


def bootstrap_database(db, host_service: HostService) -> None:
    """Первичная подготовка базы данных и импорт legacy hosts.json."""

    default_key = db.ssh_keys.default()
    if not default_key:
        private_path = Path("keys/id_ed25519")
        public_path = Path("keys/id_ed25519.pub")

        if private_path.exists():
            default_key = db.ssh_keys.create(
                name="default_key",
                private_key_path=str(private_path),
                public_key_path=str(public_path) if public_path.exists() else "",
                has_passphrase=0,
                is_default=1,
            )

    if not db.hosts.all() and Path("hosts.json").exists():
        imported = host_service.import_legacy_hosts_json(
            "hosts.json",
            ssh_key_id=default_key.id if default_key else None,
        )
        logger.info("Imported %s hosts from hosts.json", imported)


def bootstrap_task_templates(db) -> None:
    """Создание базовых шаблонов задач, если они ещё не созданы."""

    templates = [
        ("Проверка доступности", "availability_check", {}, "Проверка доступности выбранных хостов"),
        ("Сбор инвентаризации", "inventory_collect", {}, "Сбор системной информации по выбранным хостам"),
        ("Массовый SSH", "mass_ssh", {}, "Выполнение произвольной команды по SSH"),
        ("APT package manager", "apt_package_manager", {"action": "update"}, "Обновление/установка/удаление пакетов APT"),
        ("Переустановка endpoint-агента", "agent_provision", {}, "Переустановка endpoint-агента на хостах (без ротации ключа/токена, общение через netrunner-svc)"),
    ]

    for name, module_slug, default_args, description in templates:
        module_row = db.modules.by_slug(module_slug)
        if not module_row:
            continue

        existing = db.task_templates.get_one_by(name=name)
        if existing:
            continue

        db.task_templates.create(
            name=name,
            module_id=module_row.id,
            default_args_json=json.dumps(default_args, ensure_ascii=False),
            description=description,
        )


def create_app_context(
    db_path: str = "data/netrunner.db",
    reports_dir: str = "reports",
    run_scheduler_on_start: bool = True,
) -> AppContext:
    """Создаёт общий контекст NetRunner для CLI или server-GUI."""

    db = open_database(db_path)
    host_service = HostService(db)
    module_registry = ModuleRegistry(db)

    bootstrap_database(db, host_service)

    builtin_items = builtin_modules.Modules.get_all()
    user_items = user_modules_pkg.UserModules.get_all()

    module_registry.register_menu_items(builtin_items, is_builtin=True)
    module_registry.register_menu_items(user_items, is_builtin=False)
    _load_user_modules_from_disk(module_registry)
    bootstrap_task_templates(db)

    history = HistoryService(db)

    task_runner = TaskRunner(
        db=db,
        host_service=host_service,
        module_registry=module_registry,
        logger=logger,
        history=history,
    )
    scheduler = Scheduler(db=db, task_runner=task_runner, logger=logger, history=history)
    auth_service = AuthService(db=db)
    auth_service.create_default_user()
    report_service = ReportService(db=db, reports_dir=reports_dir)
    execution_settings = ExecutionSettings(db)
    scenario_runner = ScenarioRunner(
        db=db,
        host_service=host_service,
        module_registry=module_registry,
        logger=logger,
        execution_settings=execution_settings,
        history=history,
    )

    if run_scheduler_on_start:
        scheduler.tick()

    return AppContext(
        db=db,
        host_service=host_service,
        module_registry=module_registry,
        task_runner=task_runner,
        scheduler=scheduler,
        auth_service=auth_service,
        report_service=report_service,
        scenario_runner=scenario_runner,
        history=history,
        execution_settings=execution_settings,
        db_path=db_path,
        reports_dir=reports_dir,
    )


def _load_user_modules_from_disk(module_registry: ModuleRegistry) -> None:
    """Загружает пользовательские модули из /app/modules (или modules/) в реестр."""

    modules_dir = Path("/app/modules")
    if not modules_dir.exists() or not modules_dir.is_dir():
        modules_dir = Path("modules")
    if not modules_dir.exists() or not modules_dir.is_dir():
        return

    existing_slugs = {item.slug for item in module_registry.all()}

    for file_path in modules_dir.glob("*.py"):
        slug = file_path.stem
        if slug in existing_slugs:
            continue
        try:
            spec = importlib.util.spec_from_file_location(slug, str(file_path))
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            # Use a namespaced key to avoid shadowing stdlib or installed packages.
            sys.modules[f"netrunner_user.{slug}"] = module
            spec.loader.exec_module(module)
            user_cls = getattr(module, "UserModule", None)
            if user_cls is None:
                continue
            instance = user_cls()
            module_slug = getattr(instance, "slug", None) or slug
            module_registry.register_instance(instance, is_builtin=False, slug=module_slug)
        except Exception as exc:
            logger.warning("Failed to load user module %s: %s", file_path, exc)
