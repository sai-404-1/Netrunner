from . import Modules


class UserModule:
    slug = "availability_check"

    def __init__(self):
        self.title = "Проверка доступности"
        self.description = "Проверяет доступность выбранных хостов."

    def exec(self):
        print("Этот модуль должен запускаться через систему задач.")

    def _parse_ping_result(self, result: str) -> tuple[str, str]:
        result = result.strip()
        is_ok = "1 received" in result or "1 packets received" in result
        status = "OK" if is_ok else "FAIL"
        return status, result

    def run(self, context, targets, **kwargs):
        from computer import Computer

        lines = []
        ok_count = 0
        per_host_results = []

        for host in targets:
            computer = Computer(
                host=f"{host.username}@{host.address}",
                port=str(host.port),
            )
            status, result = self._parse_ping_result(computer.ping())
            if status == "OK":
                ok_count += 1

            lines.append(
                f"[{status}] {host.name} ({host.username}@{host.address}:{host.port})\n{result}"
            )
            per_host_results.append({
                "host_id": host.id,
                "name": host.name,
                "address": host.address,
                "port": host.port,
                "username": host.username,
                "status": status,
                "output": result,
            })

        lines.append(f"\nИтог: доступно {ok_count} из {len(targets)}")
        return {
            "summary_text": "\n\n".join(lines),
            "per_host_results": per_host_results,
        }

    async def run_for_host(self, context, host, **kwargs):
        """Per-host async execution used by TaskRunner."""
        import asyncio
        from computer import Computer

        to_computer = getattr(context, "to_computer", None)
        if callable(to_computer):
            try:
                computer = to_computer(host)
            except Exception:
                computer = None
        else:
            computer = None

        if computer is None:
            computer = Computer(
                host=f"{host.username}@{host.address}",
                port=str(host.port),
            )

        result = await asyncio.to_thread(computer.ping)
        status, result = self._parse_ping_result(result)

        return {
            "host_id": host.id,
            "name": host.name,
            "address": host.address,
            "port": host.port,
            "username": host.username,
            "status": status,
            "output": result,
        }


CustomModule = UserModule()
Modules.add_update(CustomModule.title, CustomModule)
