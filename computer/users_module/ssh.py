from computer import Computer
from config import HOSTS
from . import UserModules


class UserModule:
    slug = "mass_ssh"
    schema = {
        "placeholders": [
            ["command", "Команда", "uname -a", "textarea"],
        ]
    }

    def __init__(self):
        self.title = "Массовый SSH"
        self.description = "Выполнение команды на одном хосте или группе через систему задач."

    # legacy-режим оставляем, чтобы ничего не сломать
    def exec(self):
        try:
            command = input("Ожидаю ввод команды: ").strip()
            if not command:
                print("Команда пустая.")
                return

            for host in HOSTS:
                result = Computer(host).executor_ssh(command)
                print(f"{host}:\n{result}\n{'-' * 60}")
        except KeyboardInterrupt:
            print("Остановлено...")

    # TaskRunner спросит аргументы через это
    def prompt_args(self):
        command = input("Введите команду для выполнения: ").strip()
        if not command:
            return None
        return {"command": command}

    # Новый системный запуск
    def run(self, context, targets, command: str = "uname -a", **kwargs):
        outputs = []
        per_host_results = []

        for host in targets:
            computer = Computer(
                host=f"{host.username}@{host.address}",
                port=str(host.port),
            )
            result = computer.executor_ssh(command)

            outputs.append(
                f"=== {host.name} ({host.username}@{host.address}:{host.port}) ===\n{result}"
            )
            per_host_results.append({
                "host_id": host.id,
                "name": host.name,
                "address": host.address,
                "port": host.port,
                "username": host.username,
                "command": command,
                "output": result,
            })

        return {
            "summary_text": "\n\n".join(outputs),
            "per_host_results": per_host_results,
        }

    async def run_for_host(self, context, host, command: str = "uname -a", **kwargs):
        """Per-host async execution used by TaskRunner.

        Returns a dict with host metadata and the SSH command output.
        """
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

        result = await computer.async_executor_ssh(command)

        return {
            "host_id": host.id,
            "name": host.name,
            "address": host.address,
            "port": host.port,
            "username": host.username,
            "command": command,
            "output": result,
        }


CustomModule = UserModule()
UserModules.add_update(CustomModule.title, CustomModule)
