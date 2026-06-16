from . import UserModules

class UserModule:
    def __init__(self):
        self.title = "Hello two"
        self.description = """"""

    def exec(self):
        print("Hello (2)")

CustomModule = UserModule()
UserModules.add_update(CustomModule.title, CustomModule)