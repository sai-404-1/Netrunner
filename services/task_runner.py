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
    db: object | None = None
    host_service: object | None = None


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

    def __init__(self, db, host_service, module_registry, logger, history=None):
        self.db = db
        self.host_service = host_service
        self.module_registry = module_registry
        self.logger = logger
        self.history = history
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
        targets=None,
    ):
        args = args or {}
        registry_item = self.module_registry.get(module_slug)
        module_row = self.db.modules.by_slug(module_slug)

        if not module_row:
            raise RuntimeError(f"Module '{module_slug}' not found in database")
        if not module_row.is_enabled:
            raise RuntimeError(f"Module '{module_slug}' is disabled")

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

        if targets is None:
            targets = self.host_service.resolve_targets(target_type, target_id)
        context = ModuleContext(
            logger=self.logger,
            task_run_id=task_run.id,
            to_computer=self.host_service.to_computer,
            db=self.db,
            host_service=self.host_service,
        )

        if self.history:
            module_name = module_row.name or module_row.slug
            self.history.record(
                source="task",
                event_type="task_run",
                title=f"Запуск модуля {module_name}",
                description=f"Цель: {target_type}:{target_id}, {len(targets)} хостов",
                actor_name=created_by,
                payload={"module_name": module_name, "target": f"{target_type}:{target_id}", "hosts_count": len(targets)},
                ref_type="task_run",
                ref_id=task_run.id,
                level="info",
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
            module_reported_error = False
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
                module_reported_error = False
                if isinstance(result, dict):
                    stdout_text = result.get("summary_text", json.dumps(result, ensure_ascii=False, default=str))
                    per_host_results = result.get("per_host_results")
                    inventory_items = result.get("inventory_items", [])
                    if result.get("status") == "error":
                        module_reported_error = True
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

            # Check if any per-host result reported an error
            any_host_error = any(
                r.get("status") == "error" or str(r.get("output", "")).startswith("[ERROR]")
                for r in per_host_results
            )
            final_status = "error" if (module_reported_error or any_host_error) else "success"

            if self.history:
                module_name = module_row.name or module_row.slug
                self.history.record(
                    source="task",
                    event_type="task_done" if final_status == "success" else "task_failed",
                    title=f"Задача «{module_name}» завершена: {final_status}",
                    description=f"Цель: {target_type}:{target_id}, {len(targets)} хостов",
                    actor_name=created_by,
                    payload={"module_name": module_name, "target": f"{target_type}:{target_id}", "hosts_count": len(targets)},
                    ref_type="task_run",
                    ref_id=task_run.id,
                    level="success" if final_status == "success" else "error",
                )

            self.db.task_runs.finish(
                run_id=task_run.id,
                status=final_status,
                stdout_text=stdout_text,
                stderr_text="",
                exit_code=0 if final_status == "success" else 1,
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

        Если у модуля задан атрибут ``max_parallel`` (> 0), число одновременно
        обрабатываемых хостов ограничивается семафором — чтобы не нагружать сеть
        (например, при рассылке файлов). Иначе все хосты обрабатываются сразу.
        """
        max_parallel = getattr(instance, "max_parallel", None)
        semaphore = (
            asyncio.Semaphore(max_parallel)
            if isinstance(max_parallel, int) and max_parallel > 0
            else None
        )

        # Состояние каждого хоста в порядке целей: queued → running → ok|error.
        # Это даёт клиенту живую картину «сколько пройдено, кто выполняется, кто в очереди».
        order = [host.id for host in targets]
        by_id = {
            host.id: {
                "host_id": host.id,
                "name": host.name,
                "address": host.address,
                "port": host.port,
                "username": host.username,
                "state": "queued",
                "output": "",
            }
            for host in targets
        }

        def _snapshot():
            return [by_id[hid] for hid in order]

        self._save_progress(context.task_run_id, _snapshot())

        def _result_state(result: dict) -> str:
            if result.get("status") == "error" or str(result.get("output", "")).startswith("[ERROR]"):
                return "error"
            return "ok"

        async def _mark_running(host):
            by_id[host.id]["state"] = "running"
            self._save_progress(context.task_run_id, _snapshot())

        async def _run_limited(host):
            # Возвращаем (host, result), чтобы всегда знать хост, даже если модуль не
            # положил host_id. Исключения хоста превращаем в результат с ошибкой; отмену
            # (CancelledError) пробрасываем наверх.
            try:
                if semaphore is not None:
                    async with semaphore:
                        await _mark_running(host)
                        return host, await self._run_one_host(instance, context, host, args)
                await _mark_running(host)
                return host, await self._run_one_host(instance, context, host, args)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.logger.warning("Host %s (%s) failed: %s", host.name, host.address, exc)
                return host, {
                    "host_id": host.id,
                    "name": host.name,
                    "address": host.address,
                    "port": host.port,
                    "username": host.username,
                    "output": f"[ERROR] {exc}",
                }

        tasks = [asyncio.create_task(_run_limited(host), name=f"host-{host.id}") for host in targets]

        inventory_items = []
        try:
            # По мере готовности обновляем состояние конкретного хоста и сохраняем снимок.
            for coro in asyncio.as_completed(tasks):
                host, result = await coro
                by_id[host.id] = {**result, "state": _result_state(result)}
                inventory_item = result.get("inventory_item")
                if inventory_item is not None:
                    inventory_items.append(inventory_item)
                self._save_progress(context.task_run_id, _snapshot())
        except asyncio.CancelledError:
            for task in tasks:
                if not task.done():
                    task.cancel()
            raise

        return _snapshot(), inventory_items

    def _save_progress(self, task_run_id, per_host_results):
        """Сохраняет промежуточные результаты по хостам для отображения прогресса.

        Прогресс — вспомогательная информация: ошибка записи не должна валить задачу.
        """
        try:
            self.db.task_runs.update(
                task_run_id,
                per_host_json=json.dumps(per_host_results, ensure_ascii=False, default=str),
            )
        except Exception:
            pass

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
