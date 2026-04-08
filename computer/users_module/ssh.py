from computer import Computer
from config import HOSTS
from . import UserModules

class UserModule:
    def __init__(self):
        self.title = "Массовый SSH."
        self.description = """Пример использования: exec("Hello world!")"""

    def exec(self):
        try:
            command = input("Ожидаю ввод команды: ")
            for host in HOSTS:
                result = Computer(host).executor_ssh(command)
                print(f"{host}:\t{result}")
        except KeyboardInterrupt:
            print("Остановлено...")

CustomModule = UserModule()

UserModules.add_update("ssh", CustomModule)