global _UserModules
class _UserModules:
    def __init__(self):
        self.user_modules = {} # личные функции пользователя

    def add_update(self, name, module):
        self.user_modules.update({name: module})

    def call(self, name: str, *args, **kwargs):
        return self.user_modules[name].exec(*args, **kwargs)
        
    def read(self, name):
        return self.user_modules[name].description.strip()

    def get_all(self):
        return self.user_modules
    
UserModules = _UserModules()

try:
    from . import example
    from . import blacklist
    from . import ssh
except Exception as e:
    print(e)