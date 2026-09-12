from __future__ import annotations

import asyncio
import json
import traceback

from services.task_runner import ModuleContext


class ScenarioRunner:
    """Async runner for multi-step scenarios against host targets."""

    def __init__(self, db, host_service, module_registry, logger):
        self.db = db
        self.host_service = host_service
        self.module_registry = module_registry
        self.logger = logger
        self.max_parallel = 10

    async def run_scenario_async(
        self,
        scenario_id: int,
        target_type: str,
        target_id: int,
        trigger_type: str = "manual",
        scenario_run_id: int | None = None,
        hosts: list | None = None,
    ):
        scenario = self.db.scenarios.get(scenario_id)
        if not scenario:
            raise RuntimeError(f"Сценарий #{scenario_id} не найден")

        steps = self.db.scenario_steps.by_scenario(scenario_id)
        if not steps:
            raise RuntimeError(f"Сценарий '{scenario.name}' не содержит шагов")

        # Мультивыбор: вызывающий передал готовый список хостов (смесь кабинетов и
        # конкретных компов). Иначе резолвим одну цель по target_type/target_id.
        targets = hosts if hosts is not None else self.host_service.resolve_targets(target_type, target_id)
        if not targets:
            raise RuntimeError("Нет хостов для выполнения")

        # Если run-строка уже создана (фоновый запуск через API) — используем её,
        # чтобы клиент мог опрашивать прогресс по run_id. Иначе создаём новую.
        if scenario_run_id is not None:
            scenario_run = self.db.scenario_runs.get(scenario_run_id)
        else:
            scenario_run = self.db.scenario_runs.start(
                scenario_id=scenario_id,
                target_type=target_type,
                target_id=target_id,
                trigger_type=trigger_type,
            )
        self.logger.info(
            "ScenarioRun #%d: '%s' на %d хостах, %d шагов",
            scenario_run.id, scenario.name, len(targets), len(steps),
        )

        overall_status = "completed"

        for step in steps:
            success = await self._run_step_async(scenario_run.id, step, targets)
            if not success:
                if step.on_failure == "stop":
                    self.logger.info(
                        "Шаг %d '%s' упал, on_failure=stop — сценарий остановлен",
                        step.step_order, step.step_name or f"Шаг {step.step_order}",
                    )
                    overall_status = "failed"
                    break
                elif step.on_failure == "skip":
                    self.logger.info(
                        "Шаг %d '%s' упал, on_failure=skip — пропускаем",
                        step.step_order, step.step_name or f"Шаг {step.step_order}",
                    )

        self.db.scenario_runs.finish(scenario_run.id, status=overall_status)
        self.logger.info("ScenarioRun #%d завершён: %s", scenario_run.id, overall_status)
        return self.db.scenario_runs.get(scenario_run.id)

    async def _run_step_async(self, scenario_run_id: int, step, targets):
        module_row = self.db.modules.get(step.module_id)
        if not module_row:
            self.logger.error("Модуль #%d не найден", step.module_id)
            return False

        registry_item = self.module_registry.get(module_row.slug)
        if not registry_item or not registry_item.supports_task_runner:
            self.logger.error("Модуль '%s' не поддерживает task runner", module_row.slug)
            return False

        step_args = json.loads(step.config_json) if step.config_json else {}
        step_name = step.step_name or f"Шаг {step.step_order} ({module_row.name})"
        self.logger.info("  → Шаг %d: %s на %d хостах", step.step_order, step_name, len(targets))

        instance = registry_item.instance
        semaphore = asyncio.Semaphore(self.max_parallel)

        async def _run_host(host):
            async with semaphore:
                return await self._run_on_host_async(
                    instance, module_row, host, step_args,
                    scenario_run_id, step.id,
                )

        tasks = [asyncio.create_task(_run_host(host), name=f"sc-host-{host.id}") for host in targets]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        ok_count = 0
        for host, result in zip(targets, results):
            if isinstance(result, BaseException):
                self.logger.warning("  %s FAIL: %s", host.name, result)
            elif result is True:
                ok_count += 1
                self.logger.info("  %s OK", host.name)
            else:
                self.logger.warning("  %s FAIL: %s", host.name, result)

        self.logger.info("  ✓ Шаг %d: %d/%d успешно", step.step_order, ok_count, len(targets))
        return ok_count > 0

    async def _run_on_host_async(self, instance, module_row, host, step_args, scenario_run_id, step_id):
        sr = self.db.scenario_step_runs.start_step(
            scenario_run_id=scenario_run_id,
            step_id=step_id,
            host_id=host.id,
            module_id=module_row.id,
        )
        context = ModuleContext(
            logger=self.logger,
            task_run_id=sr.id,
            db=self.db,
            to_computer=self.host_service.to_computer,   # ← добавил
        )

        try:
            if hasattr(instance, "run_for_host"):
                result = await instance.run_for_host(context, host, **step_args)
                self.logger.info(f"Выполнено: {result.get('command', None)}\nРезультат: {result.get('output', None)}")
            else:
                result = await asyncio.to_thread(instance.run, context, targets=[host], **step_args)

            output = ""
            if isinstance(result, dict):
                output = result.get("output", result.get("summary_text", json.dumps(result, ensure_ascii=False, default=str)))
                if result.get("status") == "error" or str(output).startswith("[ERROR]"):
                    self.db.scenario_step_runs.finish_step(
                        sr.id, status="failed", error_text=output, exit_code=1,
                    )
                    return False
            elif isinstance(result, str):
                output = result
            else:
                output = json.dumps(result, ensure_ascii=False, default=str)

            self.db.scenario_step_runs.finish_step(
                sr.id, status="completed", output_text=output, exit_code=0,
            )
            return True
        except Exception as exc:
            err = f"{exc}\n{traceback.format_exc()}"
            self.db.scenario_step_runs.finish_step(
                sr.id, status="failed", error_text=err, exit_code=1,
            )
            return False
