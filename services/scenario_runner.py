from __future__ import annotations

import asyncio
import json
import traceback
from dataclasses import dataclass, field
from typing import Any

from services.execution_settings import MODE_BATCH, ExecutionSettings
from services.task_runner import ModuleContext


@dataclass(slots=True)
class _StepPlan:
    """Разобранный шаг сценария: модуль и аргументы резолвятся один раз на запуск,
    а не заново на каждом хосте."""

    step: Any
    module_row: Any = None
    instance: Any = None
    args: dict = field(default_factory=dict)
    error: str | None = None

    @property
    def name(self) -> str:
        module_name = getattr(self.module_row, "name", "") or f"модуль #{self.step.module_id}"
        return self.step.step_name or f"Шаг {self.step.step_order} ({module_name})"

    @property
    def on_failure(self) -> str:
        return self.step.on_failure


@dataclass(slots=True)
class _ScenarioPlan:
    """Один сценарий в очереди запуска: строка scenario_runs + разобранные шаги."""

    run_id: int
    scenario: Any
    steps: list[_StepPlan]
    pending_hosts: int = 0
    host_statuses: dict[int, str] = field(default_factory=dict)


class ScenarioRunner:
    """Async runner for multi-step scenarios against host targets.

    Модель выполнения — **пер-хост**: каждый компьютер идёт по своей очереди
    сценариев и внутри сценария по своим шагам независимо от остальных.
    Упавший хост уводит с дистанции только себя: соседи продолжают до конца.
    """

    def __init__(self, db, host_service, module_registry, logger, execution_settings=None):
        self.db = db
        self.host_service = host_service
        self.module_registry = module_registry
        self.logger = logger
        # Темп выполнения перечитывается перед каждым запуском, а не берётся
        # один раз при старте: правка настройки в админке должна работать сразу.
        self.execution_settings = execution_settings or ExecutionSettings(db)

    async def run_scenario_async(
        self,
        scenario_id: int,
        target_type: str,
        target_id: int,
        trigger_type: str = "manual",
        scenario_run_id: int | None = None,
    ):
        """Запускает один сценарий — частный случай очереди из одного элемента."""
        runs = await self.run_scenarios_async(
            scenario_ids=[scenario_id],
            target_type=target_type,
            target_id=target_id,
            trigger_type=trigger_type,
            scenario_run_ids=[scenario_run_id] if scenario_run_id is not None else None,
        )
        return runs[0]

    async def run_scenarios_async(
        self,
        scenario_ids: list[int],
        target_type: str,
        target_id: int,
        trigger_type: str = "manual",
        scenario_run_ids: list[int] | None = None,
    ):
        """Прогоняет очередь сценариев на цели.

        Очередь сценариев — своя у каждого хоста: быстрый компьютер уходит на
        следующий сценарий, не дожидаясь, пока медленный сосед добьёт текущий.
        """
        if not scenario_ids:
            raise RuntimeError("Не указан ни один сценарий")

        targets = self.host_service.resolve_targets(target_type, target_id)
        if not targets:
            raise RuntimeError("Нет хостов для выполнения")

        config = self.execution_settings.get_config()
        if config["mode"] == MODE_BATCH:
            self.logger.info(
                "Темп: пакетами по %d машин, пауза между пакетами %d с",
                config["batch_size"], config["batch_delay"],
            )
        else:
            self.logger.info("Темп: до %d машин одновременно", config["max_parallel"])

        plans: list[_ScenarioPlan] = []
        for index, scenario_id in enumerate(scenario_ids):
            scenario = self.db.scenarios.get(scenario_id)
            if not scenario:
                raise RuntimeError(f"Сценарий #{scenario_id} не найден")

            steps = self.db.scenario_steps.by_scenario(scenario_id)
            if not steps:
                raise RuntimeError(f"Сценарий '{scenario.name}' не содержит шагов")

            # Если run-строки уже созданы (фоновый запуск через API) — используем их,
            # чтобы клиент мог опрашивать прогресс по run_id. Иначе создаём новые.
            run_id = scenario_run_ids[index] if scenario_run_ids else None
            if run_id is None:
                run_id = self.db.scenario_runs.start(
                    scenario_id=scenario_id,
                    target_type=target_type,
                    target_id=target_id,
                    trigger_type=trigger_type,
                ).id

            plans.append(
                _ScenarioPlan(
                    run_id=run_id,
                    scenario=scenario,
                    steps=[self._plan_step(step) for step in steps],
                    pending_hosts=len(targets),
                )
            )
            self.logger.info(
                "ScenarioRun #%d: '%s' на %d хостах, %d шагов",
                run_id, scenario.name, len(targets), len(steps),
            )

        async def _host_queue(host):
            for plan in plans:
                status = await self._run_scenario_on_host(plan, host)
                self._report_host_finished(plan, host, status)

        results = await self._dispatch_hosts(targets, _host_queue, config)

        for host, result in zip(targets, results):
            if isinstance(result, BaseException):
                self.logger.error("Очередь сценариев на %s оборвалась: %s", host.name, result)

        # Страховка: если очередь хоста упала до отчёта, run мог остаться незакрытым.
        for plan in plans:
            if plan.pending_hosts > 0:
                plan.pending_hosts = 0
                self._finish_run(plan)

        return [self.db.scenario_runs.get(plan.run_id) for plan in plans]

    # --- темп выполнения --------------------------------------------------

    async def _dispatch_hosts(self, targets, run_host, config) -> list:
        """Запускает очередь на хостах в темпе, заданном настройкой.

        Возвращает результаты в порядке `targets` (исключения — как значения),
        чтобы вызывающий мог сопоставить их с хостами.
        """
        if config["mode"] == MODE_BATCH:
            return await self._run_in_batches(targets, run_host, config)
        return await self._run_with_limit(targets, run_host, config)

    async def _run_in_batches(self, targets, run_host, config) -> list:
        """Пакетами: следующая партия машин стартует только после того, как
        предыдущая прошла свою очередь сценариев целиком."""
        size = config["batch_size"]
        delay = config["batch_delay"]
        batches = [targets[i:i + size] for i in range(0, len(targets), size)]

        results: list = []
        for number, batch in enumerate(batches, start=1):
            self.logger.info(
                "Пакет %d/%d: %s",
                number, len(batches), ", ".join(host.name for host in batch),
            )
            tasks = [
                asyncio.create_task(run_host(host), name=f"sc-host-{host.id}")
                for host in batch
            ]
            results.extend(await asyncio.gather(*tasks, return_exceptions=True))
            if delay and number < len(batches):
                self.logger.info("Пауза %d с перед следующим пакетом", delay)
                await asyncio.sleep(delay)
        return results

    async def _run_with_limit(self, targets, run_host, config) -> list:
        """Скользящий параллелизм: освободилось место — сразу заходит следующая
        машина, партий не ждём."""
        semaphore = asyncio.Semaphore(config["max_parallel"])

        async def _guarded(host):
            async with semaphore:
                return await run_host(host)

        tasks = [
            asyncio.create_task(_guarded(host), name=f"sc-host-{host.id}")
            for host in targets
        ]
        return await asyncio.gather(*tasks, return_exceptions=True)

    # --- планирование -----------------------------------------------------

    def _plan_step(self, step) -> _StepPlan:
        """Резолвит модуль шага заранее: недоступный модуль — это ошибка шага,
        а не падение всего запуска."""
        module_row = self.db.modules.get(step.module_id)
        if not module_row:
            return _StepPlan(step=step, error=f"Модуль #{step.module_id} не найден")

        registry_item = self.module_registry.get(module_row.slug)
        if not registry_item or not registry_item.supports_task_runner:
            return _StepPlan(
                step=step,
                module_row=module_row,
                error=f"Модуль '{module_row.slug}' не поддерживает task runner",
            )

        return _StepPlan(
            step=step,
            module_row=module_row,
            instance=registry_item.instance,
            args=json.loads(step.config_json) if step.config_json else {},
        )

    # --- выполнение пер-хост ---------------------------------------------

    async def _run_scenario_on_host(self, plan: _ScenarioPlan, host) -> str:
        """Прогоняет шаги сценария на одном хосте. Возвращает статус хоста:
        completed / partial / failed."""
        had_failure = False

        for index, step_plan in enumerate(plan.steps):
            ok = await self._run_step_on_host(plan.run_id, step_plan, host)
            if ok:
                continue

            had_failure = True
            if step_plan.on_failure == "stop":
                self.logger.info(
                    "  %s: шаг %d '%s' упал, on_failure=stop — хост сходит с дистанции",
                    host.name, step_plan.step.step_order, step_plan.name,
                )
                self._skip_steps(
                    plan.run_id, plan.steps[index + 1:], host,
                    reason=f"Пропущен: шаг '{step_plan.name}' упал (on_failure=stop)",
                )
                return "failed"

            self.logger.info(
                "  %s: шаг %d '%s' упал, on_failure=%s — идём дальше",
                host.name, step_plan.step.step_order, step_plan.name, step_plan.on_failure,
            )

        return "partial" if had_failure else "completed"

    def _skip_steps(self, scenario_run_id: int, step_plans: list[_StepPlan], host, reason: str) -> None:
        """Отмечает оставшиеся шаги хоста как пропущенные — чтобы в интерфейсе было
        видно, что они не выполнялись, а не «висят в очереди»."""
        for step_plan in step_plans:
            sr = self.db.scenario_step_runs.start_step(
                scenario_run_id=scenario_run_id,
                step_id=step_plan.step.id,
                host_id=host.id,
                module_id=step_plan.step.module_id,
            )
            self.db.scenario_step_runs.finish_step(
                sr.id, status="skipped", error_text=reason, exit_code=0,
            )

    async def _run_step_on_host(self, scenario_run_id: int, step_plan: _StepPlan, host) -> bool:
        sr = self.db.scenario_step_runs.start_step(
            scenario_run_id=scenario_run_id,
            step_id=step_plan.step.id,
            host_id=host.id,
            module_id=step_plan.step.module_id,
        )

        if step_plan.error:
            self.logger.error("  %s: %s", host.name, step_plan.error)
            self.db.scenario_step_runs.finish_step(
                sr.id, status="failed", error_text=step_plan.error, exit_code=1,
            )
            return False

        self.logger.info("  → %s: шаг %d '%s'", host.name, step_plan.step.step_order, step_plan.name)
        instance = step_plan.instance
        module_row = step_plan.module_row
        context = ModuleContext(
            logger=self.logger,
            task_run_id=sr.id,
            db=self.db,
            to_computer=self.host_service.to_computer,
        )

        try:
            if hasattr(instance, "run_for_host"):
                result = await instance.run_for_host(context, host, **step_plan.args)
            else:
                result = await asyncio.to_thread(
                    instance.run, context, targets=[host], **step_plan.args
                )

            if isinstance(result, dict):
                output = result.get(
                    "output",
                    result.get("summary_text", json.dumps(result, ensure_ascii=False, default=str)),
                )
                if result.get("status") == "error" or str(output).startswith("[ERROR]"):
                    self.logger.warning("  %s FAIL: %s", host.name, output)
                    self.db.scenario_step_runs.finish_step(
                        sr.id, status="failed", error_text=output, exit_code=1,
                    )
                    return False
            elif isinstance(result, str):
                output = result
            else:
                output = json.dumps(result, ensure_ascii=False, default=str)

            self.logger.info("  %s OK", host.name)
            self.db.scenario_step_runs.finish_step(
                sr.id, status="completed", output_text=output, exit_code=0,
            )
            return True
        except Exception as exc:  # noqa: BLE001
            err = f"{exc}\n{traceback.format_exc()}"
            self.logger.warning("  %s FAIL: %s", host.name, exc)
            self.db.scenario_step_runs.finish_step(
                sr.id, status="failed", error_text=err, exit_code=1,
            )
            return False

    # --- агрегация статуса запуска ---------------------------------------

    def _report_host_finished(self, plan: _ScenarioPlan, host, status: str) -> None:
        """Хост закончил сценарий. Когда отчитались все — закрываем scenario_run."""
        plan.host_statuses[host.id] = status
        plan.pending_hosts -= 1
        if plan.pending_hosts <= 0:
            self._finish_run(plan)

    def _finish_run(self, plan: _ScenarioPlan) -> None:
        statuses = list(plan.host_statuses.values())
        if statuses and all(s == "completed" for s in statuses):
            overall = "completed"
        elif statuses and all(s == "failed" for s in statuses):
            overall = "failed"
        elif not statuses:
            overall = "failed"
        else:
            overall = "partial"

        self.db.scenario_runs.finish(plan.run_id, status=overall)
        self.logger.info(
            "ScenarioRun #%d '%s' завершён: %s (%s)",
            plan.run_id, plan.scenario.name, overall,
            ", ".join(f"host {hid}={st}" for hid, st in plan.host_statuses.items()) or "нет хостов",
        )
