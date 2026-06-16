from computer import Computer
from config import HOSTS
from . import UserModules


class UserModule:
    def __init__(self):
        self.title = "Управление service."
        self.description = """
Управление systemd-сервисом на выбранном хосте.
Действия: status/start/stop/restart/enable/disable
        """.strip()

    def exec(self):
        try:
            host = self._pick_host()
            if not host:
                print("Хост не выбран.")
                return

            service = input("Введите имя сервиса (например ssh, cron, nginx): ").strip()
            if not service:
                print("Имя сервиса пустое.")
                return

            action = input(
                "Действие [status/start/stop/restart/enable/disable]: "
            ).strip().lower()

            allowed = {"status", "start", "stop", "restart", "enable", "disable"}
            if action not in allowed:
                print("Недопустимое действие.")
                return

            if action == "status":
                command = f"sudo -n systemctl status {service} --no-pager -l"
            else:
                command = (
                    f"sudo -n systemctl {action} {service} && "
                    f'echo "\\n[OK] {action} выполнено\\n" && '
                    f"sudo -n systemctl status {service} --no-pager -l | tail -n 30"
                )

            result = Computer(host).executor_ssh(command)
            print(f"\n=== {host} ===\n{result}\n")
        except KeyboardInterrupt:
            print("\nОстановлено...")

    def _pick_host(self):
        print("Доступные компьютеры:")
        for i, host in enumerate(HOSTS, start=1):
            print(f"{i}. {host}")

        raw = input("Выберите номер: ").strip()
        if not raw.isdigit():
            return None

        idx = int(raw) - 1
        if idx < 0 or idx >= len(HOSTS):
            return None

        return HOSTS[idx]


CustomModule = UserModule()
UserModules.add_update("service_manager", CustomModule)