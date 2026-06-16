from computer import Computer
from config import HOSTS
from . import UserModules


class UserModule:
    def __init__(self):
        self.title = "Сводка по компьютеру."
        self.description = """
Показывает hostname, пользователя, uptime, kernel, IP, диск и память.
Можно запустить на одном хосте или на всех.
        """.strip()

    def exec(self):
        try:
            mode = input("1 - один хост, 2 - все хосты: ").strip()
            targets = self._pick_targets(mode)
            if not targets:
                print("Хосты не выбраны.")
                return

            command = """
echo "HOSTNAME: $(hostname)"
echo "USER: $(whoami)"
echo "UPTIME: $(uptime -p 2>/dev/null || uptime)"
echo "KERNEL: $(uname -r)"
echo "IP: $(hostname -I 2>/dev/null | xargs)"
echo
echo "[ROOT DISK]"
df -h /
echo
echo "[MEMORY]"
free -h
""".strip()

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
UserModules.add_update("host_info", CustomModule)