from computer import Computer
from config import HOSTS
from . import UserModules


class UserModule:
    def __init__(self):
        self.title = "Топ процессов."
        self.description = """
Показывает процессы с наибольшим потреблением CPU или памяти.
        """.strip()

    def exec(self):
        try:
            host = self._pick_host()
            if not host:
                print("Хост не выбран.")
                return

            mode = input("1 - по CPU, 2 - по памяти: ").strip()

            if mode == "1":
                command = "ps -eo pid,ppid,cmd,%mem,%cpu --sort=-%cpu | head -n 15"
            else:
                command = "ps -eo pid,ppid,cmd,%mem,%cpu --sort=-%mem | head -n 15"

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
UserModules.add_update("process_top", CustomModule)