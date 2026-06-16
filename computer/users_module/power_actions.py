from computer import Computer
from config import HOSTS
from . import UserModules


class UserModule:
    def __init__(self):
        self.title = "Питание компьютера."
        self.description = """
Перезагрузка или выключение выбранного компьютера.
        """.strip()

    def exec(self):
        try:
            host = self._pick_host()
            if not host:
                print("Хост не выбран.")
                return

            action = input("1 - reboot, 2 - poweroff: ").strip()
            mapping = {
                "1": "sudo -n systemctl reboot",
                "2": "sudo -n systemctl poweroff",
            }

            command = mapping.get(action)
            if not command:
                print("Неизвестное действие.")
                return

            confirm = input(f"Подтвердите действие для {host} [yes/no]: ").strip().lower()
            if confirm != "yes":
                print("Отменено.")
                return

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
UserModules.add_update("power_actions", CustomModule)