from __future__ import annotations

import asyncio

from database.repos.schedule_repo import is_schedule


class Scheduler:
    """Планировщик запуска **сценариев** по расписанию.

    Планировщик исполняет только сценарии (scenarios): каждая запланированная
    задача привязана к сценарию через `scheduled_tasks.scenario_id`. Модули-одиночки
    и `task_templates` из планировщика убраны — решение Сая 2026-09-07
    (см. wiki netrunner-offline-scheduler / netrunner-conditional-scheduler).
    Одиночный модуль = одношаговый сценарий.

    Задача срабатывает по одному из условий:
      - `run_at` наступил (по времени);
      - `wait_for_online = 1` — ждёт, пока цель (хост или хост из группы)
        не появится в сети.
    Повторение (`interval_seconds`, лимит `max_runs`) — в `schedule_repo.mark_ran`.
    """

    def __init__(self, db, scenario_runner, logger, history=None, host_service=None):
        self.db = db
        self.scenario_runner = scenario_runner
        self.logger = logger
        self.history = history
        self.host_service = host_service

    def tick(self):
        """Синхронная обёртка для окружений без event loop (старт сервера, CLI/TUI).

        Запуск сценариев — async (через ScenarioRunner), поэтому sync-контексты
        гоняют tick_async() в свежем цикле asyncio.run(). Внутри живого event loop
        tick() вызывать нельзя — там используйте tick_async().
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self.tick_async())
        else:
            raise RuntimeError(
                "Scheduler.tick() вызван внутри event loop — используйте tick_async()"
            )

    async def _wait_online_ok(self, scheduled) -> bool:
        """True, если задача с wait_for_online готова к запуску (цель в сети).

        Для цели-хост — хост отвечает по SSH (check_host_async). Для цели-группа —
        хотя бы один хост онлайн. Если host_service недоступен — считаем готовой
        (без этого планировщик не сломается, просто перестанет ждать). Задача
        остаётся включённой, пока цель не появится в сети.
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

    async def _any_target_online(self, scheduled) -> bool:
        """Есть ли онлайн-хост среди целей задачи (для recurring-слотов).

        Если host_service недоступен — считаем True (не блокируем запуск).
        """
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

    async def _run_and_mark(self, scheduled):
        try:
            if not scheduled.scenario_id:
                # Задача пережила снос шаблонов и не привязана к сценарию —
                # запускать нечего. Оставляем в покое (не выполняем и не отключаем
                # молча), просто логируем.
                self.logger.warning(
                    "Scheduled task #%s не привязана к сценарию (scenario_id пуст), пропуск",
                    scheduled.id,
                )
                return

            if not await self._wait_online_ok(scheduled):
                # Цель пока не в сети — пропускаем и оставляем задачу включённой, ждём.
                return

            # Recurring-расписание (cron по времени): если в момент слота целевые
            # хосты офлайн — слот пропускается (запускать нечего), в историю пишется
            # «попытка, цель не в сети», run_at сдвигается на следующий слот. Не
            # «догоняем» пропущенное: для выполнения по факту включения есть
            # отдельный режим «когда будет в сети» (wait_for_online).
            if is_schedule(scheduled) and not await self._any_target_online(scheduled):
                sc_name = self.db.scenarios.get(scheduled.scenario_id)
                scenario_name = sc_name.name if sc_name else f"#{scheduled.scenario_id}"
                self.logger.warning(
                    "Scheduled #%s (%s): целевые хосты офлайн, слот пропущен",
                    scheduled.id, scenario_name,
                )
                if self.history:
                    self.history.record(
                        source="scheduler",
                        event_type="scheduler_skip",
                        title="Слот пропущен: цель не в сети",
                        description=(
                            f"Сценарий \"{scenario_name}\" не запущен — "
                            f"цель {scheduled.target_type}:{scheduled.target_id} "
                            f"не в сети в момент слота"
                        ),
                        payload={
                            "task_name": f"scenario-{scheduled.scenario_id}",
                            "target": f"{scheduled.target_type}:{scheduled.target_id}",
                        },
                        level="warning",
                    )
                # Обязательно сдвигаем run_at на следующий слот — иначе задача
                # останется due навсегда и будет «пропускаться» каждый тик.
                self.db.scheduled.mark_ran(scheduled.id)
                return

            scenario = self.db.scenarios.get(scheduled.scenario_id)
            scenario_name = scenario.name if scenario else f"#{scheduled.scenario_id}"

            if self.history:
                self.history.record(
                    source="scheduler",
                    event_type="scheduler_run",
                    title="Автозапуск сценария по расписанию",
                    description=(
                        f"Сценарий \"{scenario_name}\", "
                        f"цель {scheduled.target_type}:{scheduled.target_id}"
                    ),
                    payload={
                        "task_name": f"scenario-{scheduled.scenario_id}",
                        "target": f"{scheduled.target_type}:{scheduled.target_id}",
                    },
                    level="info",
                )

            await self.scenario_runner.run_scenario_async(
                scenario_id=scheduled.scenario_id,
                target_type=scheduled.target_type,
                target_id=scheduled.target_id,
                trigger_type="scheduled",
            )
            self.db.scheduled.mark_ran(scheduled.id)
        except Exception as exc:  # noqa: BLE001
            self.logger.error("Scheduler failed for task %s: %s", scheduled.id, exc)
            if self.history:
                self.history.record(
                    source="scheduler",
                    event_type="scheduler_failed",
                    title="Автозапуск по расписанию завершился с ошибкой",
                    description=str(exc),
                    payload={"task_name": f"scenario-{scheduled.scenario_id}"},
                    level="error",
                )

    async def tick_async(self):
        """Асинхронная версия тика для фонового цикла и REST-эндпоинта.

        Находит due-задачи и запускает каждую, дожидаясь её завершения, прежде
        чем вызвать mark_ran() — так повторяющиеся задачи корректно сдвигаются.
        Все due-задачи запускаются параллельно (gather).
        """
        due_tasks = self.db.scheduled.due()

        if due_tasks:
            await asyncio.gather(*[self._run_and_mark(t) for t in due_tasks])
