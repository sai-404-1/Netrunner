from __future__ import annotations

import asyncio


class Scheduler:
    def __init__(self, db, task_runner, logger, history=None):
        self.db = db
        self.task_runner = task_runner
        self.logger = logger
        self.history = history

    def tick(self):
        due_tasks = self.db.scheduled.due()

        for scheduled in due_tasks:
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

    async def tick_async(self):
        """Asynchronous version of tick for the async server server.

        Runs each due scheduled task and waits for completion before
        calling mark_ran(), so recurring tasks advance correctly.
        """
        due_tasks = self.db.scheduled.due()

        async def _run_and_mark(scheduled):
            try:
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
