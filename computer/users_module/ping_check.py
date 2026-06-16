from computer import Computer
from config import HOSTS
from . import UserModules


class UserModule:
    def __init__(self):
        self.title = "Проверка доступности хостов."
        self.description = """Пингует все компьютеры из hosts.json."""

    def exec(self):
        try:
            print("Проверка хостов:\n")
            for host in HOSTS:
                result = Computer(host).ping()
                print(f"{host}\n{result}\n{'-' * 60}")
        except KeyboardInterrupt:
            print("\nОстановлено...")


CustomModule = UserModule()
UserModules.add_update("ping_check", CustomModule)