from . import UserModules

class UserModule:
    def __init__(self):
        self.title = "Базовая функция."
        self.description = """Пример использования: exec("Hello world!")"""

    def exec(self, *args, **kwargs):
        print(*args, **kwargs)

CustomModule = UserModule()

UserModules.add_update("example", CustomModule)
