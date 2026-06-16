from __future__ import annotations

import asyncio


class Scheduler:
    def __init__(self, db, task_runner, logger):
        self.db = db
        self.task_runner = task_runner
        self.logger = logger

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
        """Asynchronous version of tick for the async web server.

        Runs each due scheduled task in the background without blocking the
        HTTP event loop.
        """
        due_tasks = self.db.scheduled.due()

        for scheduled in due_tasks:
            try:
                asyncio.create_task(
                    self.task_runner.run_template_async(
                        template_id=scheduled.template_id,
                        target_type=scheduled.target_type,
                        target_id=scheduled.target_id,
                        trigger_type="scheduled",
                    )
                )
                self.db.scheduled.mark_ran(scheduled.id)
            except Exception as exc:
                self.logger.error("Scheduler failed for task %s: %s", scheduled.id, exc)
