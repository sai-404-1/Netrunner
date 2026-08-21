from __future__ import annotations

import base64
import importlib.util
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class RegisteredModule:
    slug: str
    title: str
    description: str
    instance: object
    is_builtin: bool
    supports_task_runner: bool
    web_ui_visible: bool = True


class ModuleRegistry:
    def __init__(self, db):
        self.db = db
        self._items: dict[str, RegisteredModule] = {}

    def _slugify(self, value: str) -> str:
        value = value.strip().lower()
        value = re.sub(r"\s+", "_", value)
        value = re.sub(r"[^a-zA-Z0-9_а-яА-Я-]", "", value)
        return value or "module"

    def register_instance(
        self,
        instance,
        is_builtin: bool = False,
        slug: str | None = None,
        name: str | None = None,
        description: str | None = None,
    ):
        title = name or getattr(instance, "title", instance.__class__.__name__)
        description = description or getattr(instance, "description", "") or ""
        class_name = instance.__class__.__name__
        module_path = instance.__class__.__module__
        slug = slug or getattr(instance, "slug", None) or self._slugify(title)

        record = RegisteredModule(
            slug=slug,
            title=title,
            description=description,
            instance=instance,
            is_builtin=is_builtin,
            supports_task_runner=hasattr(instance, "run") or hasattr(instance, "run_for_host"),
            web_ui_visible=getattr(instance, "web_ui_visible", True),
        )
        self._items[slug] = record

        existing = self.db.modules.by_slug(slug)
        schema = getattr(instance, "schema", None)
        command = getattr(instance, "command", None)
        if schema or command:
            merged = dict(schema) if schema else {}
            if command:
                merged["command"] = command
            schema_json = json.dumps(merged, ensure_ascii=False)
        else:
            schema_json = None
        payload = {
            "name": title,
            "slug": slug,
            "module_path": module_path,
            "class_name": class_name,
            "is_builtin": 1 if is_builtin else 0,
            "description": description,
            "schema_json": schema_json,
        }

        if existing:
            # Do not overwrite is_enabled — respect the operator's choice.
            self.db.modules.update(existing.id, **payload)
        else:
            self.db.modules.create(**payload, is_enabled=1)

        return record

    def register_menu_items(self, items: list[dict], is_builtin: bool = False):
        for item in items:
            instance = item["exec"]
            self.register_instance(instance=instance, is_builtin=is_builtin)

    def get(self, slug: str) -> RegisteredModule:
        return self._items[slug]

    def all(self):
        return list(self._items.values())

    def menu_items(self, db=None, task_runner=None):
        items = []

        if db is not None and task_runner is not None:
            from services.menu_actions import RunRegisteredModuleAction

            for item in self._items.values():
                items.append(
                    {
                        "title": item.title,
                        "exec": RunRegisteredModuleAction(
                            db=db,
                            task_runner=task_runner,
                            registry_item=item,
                        ),
                    }
                )
            return items

        return [{"title": item.title, "exec": item.instance} for item in self._items.values()]

def _install_uploaded_module(
        ctx,
        slug: str,
        module_path: str,
        file_data: str,
        name: str | None = None,
        description: str | None = None,
) -> None:
    """Сохраняет загруженный .py-файл и импортирует класс UserModule в runtime."""
    modules_dir = Path("/app/modules")
    modules_dir.mkdir(parents=True, exist_ok=True)

    file_name = Path(module_path).name
    if not file_name.endswith(".py"):
        file_name = f"{slug}.py"
    target_path = modules_dir / file_name

    raw = base64.b64decode(file_data)
    target_path.write_bytes(raw)

    spec = importlib.util.spec_from_file_location(slug, str(target_path))
    if spec is None or spec.loader is None:
        raise RuntimeError("Не удалось создать spec для модуля")
    module = importlib.util.module_from_spec(spec)
    sys.modules[slug] = module
    spec.loader.exec_module(module)

    user_cls = getattr(module, "UserModule", None)
    if user_cls is None:
        raise RuntimeError("В модуле не найден класс UserModule")

    instance = user_cls()
    ctx.module_registry.register_instance(
        instance,
        is_builtin=False,
        slug=slug,
        name=name,
        description=description,
    )