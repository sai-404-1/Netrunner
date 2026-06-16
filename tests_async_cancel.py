"""Example/test for async per-host task execution and cancellation.

Usage:
    python tests_async_cancel.py

The script creates a temporary SQLite database, a few fake hosts, a fake async
module that sleeps per host, and then:
  1. Runs the module on a group of 4 hosts concurrently.
  2. Cancels a running task and verifies the DB record is marked 'cancelled'.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import tempfile
import time
import types

# The project expects a `config` module at import time. Provide a minimal fake
# config so the test can run without a real deployment config file.
_config = types.ModuleType("config")
_config.KEY_NAME = "id_ed25519"
_config.KEY_PATH = "/tmp/keys"
_config.SSH_STRICT_HOST_KEY_CHECKING = "no"
_config.HOSTS = []
sys.modules["config"] = _config

from computer.module.executor_ssh import async_main
from database import open_database
from services import HostService, ModuleRegistry, TaskRunner


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("netrunner.test")


class SlowEchoModule:
    """Fake async module that simulates a slow per-host operation."""

    slug = "slow_echo"

    def __init__(self):
        self.title = "Slow Echo"
        self.description = "Async per-host test module for cancellation"

    def run(self, context, targets, sleep_seconds: float = 0.5, **kwargs):
        # Legacy sync wrapper (not used by the new runner, but keeps API intact).
        return asyncio.run(self.run_async(context, targets, sleep_seconds=sleep_seconds, **kwargs))

    async def run_async(self, context, targets, sleep_seconds: float = 0.5, **kwargs):
        tasks = [self.run_for_host(context, host, sleep_seconds=sleep_seconds) for host in targets]
        results = await asyncio.gather(*tasks)
        return {
            "summary_text": "\n".join(r["output"] for r in results),
            "per_host_results": results,
        }

    async def run_for_host(self, context, host, sleep_seconds: float = 0.5, **kwargs):
        await asyncio.sleep(sleep_seconds)
        return {
            "host_id": host.id,
            "name": host.name,
            "address": host.address,
            "port": host.port,
            "username": host.username,
            "output": f"echo from {host.name}",
        }


def _setup():
    db_path = tempfile.mktemp(suffix=".db")
    db = open_database(db_path)
    host_service = HostService(db)

    hosts = []
    for i in range(1, 5):
        host = host_service.add_host(
            name=f"host-{i}",
            address=f"10.0.0.{i}",
            username="root",
            port=22,
        )
        hosts.append(host)

    group = host_service.create_group("test-group")
    for host in hosts:
        host_service.add_host_to_group(group.id, host.id)

    return db, host_service, group.id, db_path


def _teardown(db, db_path: str) -> None:
    db.close()
    if os.path.exists(db_path):
        os.remove(db_path)


def test_concurrent_run() -> None:
    """Run a task on 4 hosts concurrently and verify completion time."""
    db, host_service, group_id, db_path = _setup()
    try:
        module_registry = ModuleRegistry(db)
        module_registry.register_instance(SlowEchoModule(), is_builtin=False, slug="slow_echo")

        runner = TaskRunner(db, host_service, module_registry, logger)

        sleep_seconds = 0.5
        start = time.monotonic()
        run = runner.run(
            module_slug="slow_echo",
            target_type="group",
            target_id=group_id,
            args={"sleep_seconds": sleep_seconds},
        )
        elapsed = time.monotonic() - start

        assert run.status == "success", f"Expected success, got {run.status}"
        assert run.per_host_json is not None
        per_host = json.loads(run.per_host_json)
        assert len(per_host) == 4, f"Expected 4 results, got {len(per_host)}"

        # Concurrent: 4 hosts each sleeping 0.5s should take much less than 2s.
        assert elapsed < sleep_seconds * 4 * 0.75, f"Run was not concurrent enough: {elapsed:.2f}s"

        print(f"[PASS] Concurrent run finished in {elapsed:.2f}s (status={run.status})")
    finally:
        _teardown(db, db_path)


def test_cancel() -> None:
    """Cancel a running task and verify it is marked 'cancelled'."""
    db, host_service, group_id, db_path = _setup()
    try:
        module_registry = ModuleRegistry(db)
        module_registry.register_instance(SlowEchoModule(), is_builtin=False, slug="slow_echo")

        runner = TaskRunner(db, host_service, module_registry, logger)

        async def run_and_cancel():
            task = asyncio.create_task(
                runner.run_async(
                    module_slug="slow_echo",
                    target_type="group",
                    target_id=group_id,
                    args={"sleep_seconds": 2.0},
                )
            )
            # Give the runner a moment to start per-host tasks.
            await asyncio.sleep(0.1)
            cancelled = runner.cancel()
            assert cancelled, "cancel() should have cancelled a running task"
            try:
                await task
            except asyncio.CancelledError:
                pass
            # The DB record is updated by the runner even on cancellation.
            recent = runner.db.task_runs.list_recent(1)
            return recent[0] if recent else None

        run = asyncio.run(run_and_cancel())
        assert run is not None, "No task run found"
        assert run.status == "cancelled", f"Expected cancelled, got {run.status}"
        print(f"[PASS] Task run {run.id} was cancelled (status={run.status})")
    finally:
        _teardown(db, db_path)


def test_async_ssh_cancellation() -> None:
    """Verify that async_main can be cancelled via asyncio.Task.cancel()."""

    async def fake_create_subprocess(*args, **kwargs):
        class FakeProc:
            async def communicate(self):
                await asyncio.sleep(10)
                return b"", b""

            async def wait(self):
                await asyncio.sleep(10)
                return 0

            returncode = 0

            def kill(self):
                pass

        return FakeProc()

    original = asyncio.create_subprocess_exec
    asyncio.create_subprocess_exec = fake_create_subprocess  # type: ignore[assignment]
    try:

        async def run():
            task = asyncio.create_task(async_main("user@host", "22", "echo hi"))
            await asyncio.sleep(0.05)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                return True
            return False

        cancelled = asyncio.run(run())
        assert cancelled, "async_main should have been cancelled"
        print("[PASS] async SSH executor cancelled successfully")
    finally:
        asyncio.create_subprocess_exec = original  # type: ignore[assignment]


def main():
    test_concurrent_run()
    test_cancel()
    test_async_ssh_cancellation()
    print("\nAll tests passed.")


if __name__ == "__main__":
    main()
