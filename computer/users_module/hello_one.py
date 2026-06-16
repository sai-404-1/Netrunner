from . import UserModules

class UserModule:
    def __init__(self):
        self.title = "Hello one"
        self.description = """"""

    def exec(self):
        print("Hello (1)")

CustomModule = UserModule()
UserModules.add_update(CustomModule.title, CustomModule)