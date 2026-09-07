from __future__ import annotations

import asyncio


class Scheduler:
    def __init__(self, db, task_runner, logger, history=None, host_service=None):
        self.db = db
        self.task_runner = task_runner
        self.logger = logger
        self.history = history
        self.host_service = host_service

    def tick(self):
        due_tasks = self.db.scheduled.due()

        for scheduled in due_tasks:
            # wait_for_online обрабатывает только tick_async (асинхронный фоновый
            # цикл): тут нельзя дёргать host_service (async), а синхронный стартовый
            # тик не должен выполнять задачу, ждущую включения хоста.
            if getattr(scheduled, "wait_for_online", 0):
                continue
            try:
                self.task_runner.run_template(
                    template_id=scheduled.template_id,
                    target_type=scheduled.target_type,
                    target_id=scheduled.target_id,
                    trigger_type="scheduled",
                )
                self.db.scheduled.mark_ran(scheduled.id)
            except Exception as exc:
                self.logger.error("Scheduler failed for task %s: %s", scheduled.id, exc)

    async def _wait_online_ok(self, scheduled) -> bool:
        """True, если задача с wait_for_online готова к запуску (цель в сети).

        Для цели-хост — хост отвечает по SSH (check_host_async). Для цели-группа —
        хост онлайн. Если host_service недоступен — считаем готовой (без этого
        планировщик не сломается, просто перестанет ждать). Задача остаётся
        включённой, пока цель не появится в сети.
        """
        if not scheduled.wait_for_online:
            return True
        if not self.host_service:
            return True
        try:
            targets = self.host_service.resolve_targets(
                scheduled.target_type, scheduled.target_id
            )
        except Exception:  # noqa: BLE001
            return False
        if not targets:
            return False
        checks = await asyncio.gather(
            *[self._host_online(h) for h in targets],
            return_exceptions=True,
        )
        return any(c is True for c in checks)

    async def _host_online(self, host) -> bool:
        try:
            result = await self.host_service.check_host_async(host.id)
            return bool(result.get("is_active"))
        except Exception:  # noqa: BLE001
            return False

    async def tick_async(self):
        """Asynchronous version of tick for the async server server.

        Runs each due scheduled task and waits for completion before
        calling mark_ran(), so recurring tasks advance correctly.
        """
        due_tasks = self.db.scheduled.due()

        async def _run_and_mark(scheduled):
            try:
                if not await self._wait_online_ok(scheduled):
                    # Хост пока не в сети — пропускаем и оставляем задачу включённой, ждём.
                    return
                if self.history:
                    self.history.record(
                        source="scheduler",
                        event_type="scheduler_run",
                        title="Автозапуск по расписанию",
                        description=f"Шаблон #{scheduled.template_id}, цель {scheduled.target_type}:{scheduled.target_id}",
                        payload={"task_name": f"template-{scheduled.template_id}", "target": f"{scheduled.target_type}:{scheduled.target_id}"},
                        level="info",
                    )
                await self.task_runner.run_template_async(
                    template_id=scheduled.template_id,
                    target_type=scheduled.target_type,
                    target_id=scheduled.target_id,
                    trigger_type="scheduled",
                )
                self.db.scheduled.mark_ran(scheduled.id)
            except Exception as exc:
                self.logger.error("Scheduler failed for task %s: %s", scheduled.id, exc)
                if self.history:
                    self.history.record(
                        source="scheduler",
                        event_type="scheduler_failed",
                        title="Автозапуск по расписанию завершился с ошибкой",
                        description=str(exc),
                        payload={"task_name": f"template-{scheduled.template_id}"},
                        level="error",
                    )

        # Run all due tasks concurrently, but each marks itself ran after completion.
        if due_tasks:
            await asyncio.gather(*[_run_and_mark(t) for t in due_tasks])
