from __future__ import annotations

import asyncio
import inspect
import json
import traceback
from dataclasses import dataclass

from database.repos.base import utcnow_iso


@dataclass(slots=True)
class ModuleContext:
    logger: object
    task_run_id: int
    to_computer: object | None = None


class TaskRunner:
    """Runs modules against targets with async per-host execution and cancellation.

    Public API:
      - run(...)         synchronous wrapper around run_async(); may be called from
                         any non-async context. It uses asyncio.run() internally.
      - run_async(...)   coroutine that performs the actual concurrent execution.
      - cancel()         cancel the task currently executing in this runner.

    Modules may implement either:
      - run(context, targets, **kwargs) for legacy/sequential execution, or
      - run_for_host(context, host, **kwargs) for per-host concurrent execution.

    Per-host results are logged as soon as they arrive via the context logger.
    """

    def __init__(self, db, host_service, module_registry, logger):
        self.db = db
        self.host_service = host_service
        self.module_registry = module_registry
        self.logger = logger
        self._running_tasks: dict[int, asyncio.Task] = {}

    def cancel(self, run_id: int | None = None) -> bool:
        """Cancel one or all running tasks tracked by this runner.

        If ``run_id`` is provided, only the task for that run is cancelled.
        Otherwise every tracked running task is cancelled.

        Cancelling a task also cancels all in-flight per-host calls because they
        are child tasks of the main runner task.
        """
        if run_id is not None:
            task = self._running_tasks.get(run_id)
            if task is None or task.done():
                return False
            task.cancel()
            return True

        active = [task for task in self._running_tasks.values() if not task.done()]
        if not active:
            return False

        for task in active:
            task.cancel()
        return True

    def run(
        self,
        module_slug: str,
        target_type: str,
        target_id: int,
        args: dict | None = None,
        trigger_type: str = "manual",
        task_run_id: int | None = None,
    ):
        """Run a module synchronously. Use run_async() from async contexts."""
        try:
            return asyncio.run(
                self.run_async(
                    module_slug=module_slug,
                    target_type=target_type,
                    target_id=target_id,
                    args=args,
                    trigger_type=trigger_type,
                    task_run_id=task_run_id,
                )
            )
        except asyncio.CancelledError as exc:
            # asyncio.run() suppresses CancelledError from the main task; re-raise
            # as a normal exception so callers see a clear failure.
            raise RuntimeError("Task was cancelled") from exc

    async def run_async(
        self,
        module_slug: str,
        target_type: str,
        target_id: int,
        args: dict | None = None,
        trigger_type: str = "manual",
        task_run_id: int | None = None,
        created_by: str | None = None,
    ):
        args = args or {}
        registry_item = self.module_registry.get(module_slug)
        module_row = self.db.modules.by_slug(module_slug)

        if not module_row:
            raise RuntimeError(f"Module '{module_slug}' not found in database")

        if task_run_id is not None:
            task_run = self.db.task_runs.get(task_run_id)
            if task_run is None:
                raise RuntimeError(f"Task run #{task_run_id} not found")
            task_run = self.db.task_runs.update(
                task_run_id,
                module_id=module_row.id,
                target_type=target_type,
                target_id=target_id,
                args_json=json.dumps(args, ensure_ascii=False),
                trigger_type=trigger_type,
                status="running",
                started_at=utcnow_iso(),
            )
        else:
            task_run = self.db.task_runs.start(
                module_id=module_row.id,
                target_type=target_type,
                target_id=target_id,
                args_json=json.dumps(args, ensure_ascii=False),
                trigger_type=trigger_type,
                created_by=created_by,
            )

        targets = self.host_service.resolve_targets(target_type, target_id)
        context = ModuleContext(
            logger=self.logger,
            task_run_id=task_run.id,
            to_computer=self.host_service.to_computer,
        )

        current = asyncio.current_task()
        if current is not None:
            self._running_tasks[task_run.id] = current
        try:
            if not registry_item.supports_task_runner:
                raise RuntimeError(
                    f"Module '{module_slug}' is legacy-only. "
                    f"Add run(context, targets, **kwargs) to make it schedulable."
                )

            instance = registry_item.instance
            if hasattr(instance, "run_for_host"):
                per_host_results, inventory_items = await self._run_per_host(
                    instance=instance,
                    context=context,
                    targets=targets,
                    args=args,
                )
                stdout_text = "\n\n".join(
                    result.get("output", "") for result in per_host_results
                )
            else:
                # Fallback: run the module's synchronous run() in a worker thread.
                result = await asyncio.to_thread(
                    instance.run,
                    context=context,
                    targets=targets,
                    **args,
                )
                stdout_text = ""
                per_host_results = None
                inventory_items = []
                if isinstance(result, dict):
                    stdout_text = result.get("summary_text", json.dumps(result, ensure_ascii=False, default=str))
                    per_host_results = result.get("per_host_results")
                    inventory_items = result.get("inventory_items", [])
                elif isinstance(result, str):
                    stdout_text = result
                else:
                    stdout_text = json.dumps(result, ensure_ascii=False, default=str)

            for item in inventory_items:
                self.db.inventory.create(**item)

            if per_host_results is None:
                per_host_results = [
                    {
                        "host_id": host.id,
                        "name": host.name,
                        "address": host.address,
                        "port": host.port,
                        "username": host.username,
                        "output": stdout_text,
                    }
                    for host in targets
                ]

            self.db.task_runs.finish(
                run_id=task_run.id,
                status="success",
                stdout_text=stdout_text,
                stderr_text="",
                exit_code=0,
                per_host_json=json.dumps(per_host_results, ensure_ascii=False, default=str) if per_host_results else None,
            )
            return self.db.task_runs.get(task_run.id)

        except asyncio.CancelledError:
            self.db.task_runs.finish(
                run_id=task_run.id,
                status="cancelled",
                stdout_text="",
                stderr_text="Task was cancelled by user",
                exit_code=1,
            )
            raise
        except Exception as exc:
            self.db.task_runs.finish(
                run_id=task_run.id,
                status="error",
                stdout_text="",
                stderr_text=f"{exc}\n\n{traceback.format_exc()}",
                exit_code=1,
            )
            raise
        finally:
            if current is not None:
                self._running_tasks.pop(task_run.id, None)

    async def _run_per_host(self, instance, context, targets, args):
        """Run a module's run_for_host for every target concurrently.

        Returns (per_host_results, inventory_items). Each completed host response is
        logged immediately via the context logger. Exceptions from individual hosts
        are recorded as failed results instead of failing the whole task.
        """
        tasks = [
            asyncio.create_task(
                self._run_one_host(instance, context, host, args),
                name=f"host-{host.id}",
            )
            for host in targets
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        per_host_results = []
        inventory_items = []
        for host, result in zip(targets, results):
            if isinstance(result, BaseException):
                self.logger.warning(
                    "Host %s (%s) failed: %s",
                    host.name,
                    host.address,
                    result,
                )
                per_host_results.append(
                    {
                        "host_id": host.id,
                        "name": host.name,
                        "address": host.address,
                        "port": host.port,
                        "username": host.username,
                        "output": f"[ERROR] {result}",
                    }
                )
            else:
                per_host_results.append(result)
                inventory_item = result.get("inventory_item")
                if inventory_item is not None:
                    inventory_items.append(inventory_item)

        return per_host_results, inventory_items

    async def _run_one_host(self, instance, context, host, args):
        """Run a module for a single host and log the result as soon as it arrives."""
        self.logger.info(
            "task_run=%s start host=%s (%s)",
            context.task_run_id,
            host.name,
            host.address,
        )

        if inspect.iscoroutinefunction(instance.run_for_host):
            result = await instance.run_for_host(context, host, **args)
        else:
            result = await asyncio.to_thread(instance.run_for_host, context, host, **args)

        output = result.get("output", "")
        status = result.get("status")
        log_detail = status if status else (output[:200] if output else "done")
        self.logger.info(
            "task_run=%s response host=%s (%s): %s",
            context.task_run_id,
            host.name,
            host.address,
            log_detail,
        )
        return result

    def run_template(self, template_id: int, target_type: str, target_id: int, trigger_type: str = "manual"):
        template = self.db.task_templates.get(template_id)
        if not template:
            raise RuntimeError(f"Template #{template_id} not found")

        args = {}
        if template.default_args_json:
            args = json.loads(template.default_args_json)

        module_row = self.db.modules.get(template.module_id)
        return self.run(
            module_slug=module_row.slug,
            target_type=target_type,
            target_id=target_id,
            args=args,
            trigger_type=trigger_type,
        )

    async def run_template_async(
        self,
        template_id: int,
        target_type: str,
        target_id: int,
        trigger_type: str = "manual",
        task_run_id: int | None = None,
    ):
        """Asynchronous version of run_template for use in the async web server."""
        template = self.db.task_templates.get(template_id)
        if not template:
            raise RuntimeError(f"Template #{template_id} not found")

        args = {}
        if template.default_args_json:
            args = json.loads(template.default_args_json)

        module_row = self.db.modules.get(template.module_id)
        return await self.run_async(
            module_slug=module_row.slug,
            target_type=target_type,
            target_id=target_id,
            args=args,
            trigger_type=trigger_type,
            task_run_id=task_run_id,
        )
