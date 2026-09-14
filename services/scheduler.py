from __future__ import annotations

import asyncio

from database.repos.schedule_repo import (
    is_schedule,
    task_done_host_ids,
    task_scenario_ids,
    task_target_ids,
)


class Scheduler:
    """Планировщик запуска **сценариев** по расписанию.

    Планировщик исполняет только сценарии (scenarios): каждая запланированная
    задача привязана к сценарию через `scheduled_tasks.scenario_id`. Модули-одиночки
    и `task_templates` из планировщика убраны.
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

    def _resolve_multi_targets(self, scheduled) -> list:
        """Хосты цели задачи с учётом мульти-выбора (JSON) или legacy-полей.

        Return: список хостов (Host). Для мульти (target_host_ids_json /
        target_group_ids_json) — resolve_scheduled_targets; иначе одиночный
        resolve_targets по target_type/target_id.
        """
        host_ids, group_ids = task_target_ids(scheduled)
        if not self.host_service:
            return []
        if host_ids or group_ids:
            return self.host_service.resolve_scheduled_targets(host_ids, group_ids)
        # legacy: одиночная цель
        return self.host_service.resolve_targets(
            scheduled.target_type, scheduled.target_id
        )

    def _scenario_names(self, scenario_ids: list[int]) -> str:
        """Человекочитаемое имя сценария(ев) для логов/истории."""
        if len(scenario_ids) == 1:
            sc = self.db.scenarios.get(scenario_ids[0])
            return sc.name if sc else f"#{scenario_ids[0]}"
        names = []
        for sid in scenario_ids:
            sc = self.db.scenarios.get(sid)
            names.append(sc.name if sc else f"#{sid}")
        return ", ".join(names) if names else str(scenario_ids)

    def _target_label(self, scheduled) -> str:
        """Подпись цели задачи (для логов/истории), с учётом мульти-выбора."""
        host_ids, group_ids = task_target_ids(scheduled)
        if host_ids or group_ids:
            parts = []
            if host_ids:
                parts.append(f"hosts={host_ids}")
            if group_ids:
                parts.append(f"groups={group_ids}")
            return " + ".join(parts)
        return f"{scheduled.target_type}:{scheduled.target_id}"

    async def _hosts_online(self, hosts) -> list:
        """Возвращает подмножество хостов, которые сейчас в сети (по SSH-пингу).

        Проверки идут параллельно; исключение/таймаут хоста = «не в сети».
        """
        if not hosts:
            return []
        checks = await asyncio.gather(
            *[self._host_online(h) for h in hosts],
            return_exceptions=True,
        )
        return [h for h, ok in zip(hosts, checks) if ok is True]

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
            targets = self._resolve_multi_targets(scheduled)
        except Exception:  # noqa: BLE001
            return False
        if not targets:
            return False
        checks = await asyncio.gather(
            *[self._host_online(h) for h in targets],
            return_exceptions=True,
        )
        return any(c is True for c in checks)

    async def _run_wait_for_online(self, scheduled, scenario_ids: list[int]) -> None:
        """Режим «когда цель появится в сети» — по каждому компьютеру отдельно.

        Группа здесь НЕ является отдельной сущностью-целью: она раскрывается в
        конкретные хосты (`resolve_scheduled_targets` / `resolve_targets`). Логика:

        1. берём все хосты цели;
        2. выкидываем те, где сценарий уже отработал (прогресс `done_host_ids`);
        3. «просыпаемся» по первому онлайн-хосту — но выполняем ТОЛЬКО на тех
           оставшихся хостах, что сейчас в сети;
        4. отработавшие отмечаются в прогрессе; офлайн-хосты продолжают ждать —
           задача остаётся включённой и при следующем тике попробует их снова;
        5. когда покрыты все хосты цели — задача закрывается (`mark_ran`).

        Так один включившийся компьютер кабинета запускает сценарий только на
        себе, а не на всём кабинете.
        """
        if not self.host_service:
            return
        try:
            all_targets = self._resolve_multi_targets(scheduled)
        except Exception:  # noqa: BLE001
            return
        if not all_targets:
            return

        done = set(task_done_host_ids(scheduled))
        pending = [host for host in all_targets if host.id not in done]
        if not pending:
            # Все хосты цели уже отработали — закрываем задачу.
            self.db.scheduled.mark_ran(scheduled.id)
            return

        online = await self._hosts_online(pending)
        if not online:
            # Никто из оставшихся не в сети — ждём, задачу не трогаем.
            self.logger.info(
                "Scheduled #%s: цель не в сети, ожидание (%d хостов ещё ждут)",
                scheduled.id, len(pending),
            )
            return

        scenario_name = self._scenario_names(scenario_ids)
        target_label = self._target_label(scheduled)

        if self.history:
            self.history.record(
                source="scheduler",
                event_type="scheduler_run",
                title="Автозапуск сценария по появлению в сети",
                description=(
                    f'Сценарий "{scenario_name}", цель {target_label}; '
                    f"в сети {len(online)} из {len(all_targets)} хостов — "
                    f"запуск только на них"
                ),
                payload={
                    "task_name": f"scenario-{scenario_ids}",
                    "target": target_label,
                    "scenario_ids": scenario_ids,
                    "host_ids": [h.id for h in all_targets],
                },
                level="info",
            )

        await self.scenario_runner.run_scenarios_async(
            scenario_ids=scenario_ids,
            target_type=scheduled.target_type,
            target_id=scheduled.target_id or 0,
            trigger_type="scheduled",
            targets=online,
        )

        # Отработавшие хосты — в прогресс, чтобы не запускать их повторно.
        self.db.scheduled.mark_hosts_done(scheduled.id, [host.id for host in online])

        refreshed = self.db.scheduled.get(scheduled.id)
        remaining = [
            host for host in all_targets
            if host.id not in set(task_done_host_ids(refreshed))
        ]
        if not remaining:
            # Покрыты все хосты цели — задача выполнена, закрываем.
            self.db.scheduled.mark_ran(scheduled.id)
        else:
            self.logger.info(
                "Scheduled #%s: выполнено на %d хостах, %d ещё ждут выхода в сеть",
                scheduled.id, len(online), len(remaining),
            )

    async def _run_and_mark(self, scheduled):
        try:
            scenario_ids = task_scenario_ids(scheduled)
            if not scenario_ids:
                # Задача пережила снос шаблонов и не привязана к сценарию —
                # запускать нечего. Оставляем в покое (не выполняем и не отключаем
                # молча), просто логируем.
                self.logger.warning(
                    "Scheduled task #%s не привязана к сценарию (не указан сценарий), пропуск",
                    scheduled.id,
                )
                return

            # Режим «когда цель появится в сети» (wait_for_online) — отдельная
            # пер-хостовая обработка: группа раскрывается в конкретные компьютеры,
            # сценарий выполняется только на тех, что сейчас онлайн, а офлайн
            # продолжают ждать (см. _run_wait_for_online).
            if scheduled.wait_for_online and not is_schedule(scheduled):
                await self._run_wait_for_online(scheduled, scenario_ids)
                return

            # Recurring-расписание (cron по времени): если в момент слота целевые
            # хосты офлайн — слот пропускается (запускать нечего), в историю пишется
            # «попытка, цель не в сети», run_at сдвигается на следующий слот. Не
            # «догоняем» пропущенное: для выполнения по факту включения есть
            # отдельный режим «когда будет в сети» (wait_for_online).
            if is_schedule(scheduled) and not await self._any_target_online(scheduled):
                scenario_name = self._scenario_names(scenario_ids)
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
                            f"цель {self._target_label(scheduled)} "
                            f"не в сети в момент слота"
                        ),
                        payload={
                            "task_name": f"scenario-{scenario_ids}",
                            "target": self._target_label(scheduled),
                            "scenario_ids": scenario_ids,
                            "host_ids": [h.id for h in self._resolve_multi_targets(scheduled)],
                        },
                        level="warning",
                    )
                # Обязательно сдвигаем run_at на следующий слот — иначе задача
                # останется due навсегда и будет «пропускаться» каждый тик.
                self.db.scheduled.mark_ran(scheduled.id)
                return

            scenario_name = self._scenario_names(scenario_ids)
            targets = self._resolve_multi_targets(scheduled)
            target_label = self._target_label(scheduled)

            if self.history:
                self.history.record(
                    source="scheduler",
                    event_type="scheduler_run",
                    title="Автозапуск сценария по расписанию",
                    description=(
                        f"Сценарий \"{scenario_name}\", "
                        f"цель {target_label}"
                    ),
                    payload={
                        "task_name": f"scenario-{scenario_ids}",
                        "target": target_label,
                        "scenario_ids": scenario_ids,
                        "host_ids": [h.id for h in targets],
                    },
                    level="info",
                )

            await self.scenario_runner.run_scenarios_async(
                scenario_ids=scenario_ids,
                target_type=scheduled.target_type,
                target_id=scheduled.target_id or 0,
                trigger_type="scheduled",
                targets=targets,
            )
            self.db.scheduled.mark_ran(scheduled.id)
        except Exception as exc:  # noqa: BLE001
            self.logger.error("Scheduler failed for task %s: %s", scheduled.id, exc)
            if self.history:
                try:
                    failed_host_ids = [h.id for h in self._resolve_multi_targets(scheduled)]
                except Exception:  # noqa: BLE001
                    failed_host_ids = []
                self.history.record(
                    source="scheduler",
                    event_type="scheduler_failed",
                    title="Автозапуск по расписанию завершился с ошибкой",
                    description=str(exc),
                    payload={"task_name": f"scenario-{scheduled.scenario_id}", "host_ids": failed_host_ids},
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
