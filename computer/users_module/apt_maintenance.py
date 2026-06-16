from computer import Computer
from config import HOSTS
from . import UserModules


class UserModule:
    def __init__(self):
        self.title = "APT обслуживание."
        self.description = """
Для Debian/Ubuntu/Mint:
1 - apt update
2 - список обновлений
3 - apt upgrade -y
4 - apt autoremove -y
        """.strip()

    def exec(self):
        try:
            mode = input("1 - один хост, 2 - все хосты: ").strip()
            targets = self._pick_targets(mode)
            if not targets:
                print("Хосты не выбраны.")
                return

            print(self.description)
            action = input("Выберите действие [1/2/3/4]: ").strip()
            commands = {
                "1": "sudo -n apt update",
                "2": "apt list --upgradable 2>/dev/null",
                "3": "sudo -n apt upgrade -y",
                "4": "sudo -n apt autoremove -y",
            }

            command = commands.get(action)
            if not command:
                print("Неизвестное действие.")
                return

            for host in targets:
                result = Computer(host).executor_ssh(command)
                print(f"\n=== {host} ===\n{result}\n")
        except KeyboardInterrupt:
            print("\nОстановлено...")

    def _pick_targets(self, mode):
        if mode == "2":
            return HOSTS

        print("Доступные компьютеры:")
        for i, host in enumerate(HOSTS, start=1):
            print(f"{i}. {host}")

        raw = input("Выберите номер: ").strip()
        if not raw.isdigit():
            return []

        idx = int(raw) - 1
        if idx < 0 or idx >= len(HOSTS):
            return []

        return [HOSTS[idx]]


CustomModule = UserModule()
UserModules.add_update("apt_maintenance", CustomModule)