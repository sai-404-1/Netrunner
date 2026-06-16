global _UserModules
class _UserModules:
    def __init__(self):
        self.user_modules = [] # личные функции пользователя

    def add_update(self, name, module):
        self.user_modules.append({'title': name, 'exec': module})

    def call(self, position: int, *args, **kwargs):
        return self.user_modules[position]['exec'](*args, **kwargs)
        
    def read(self, position):
        return self.user_modules[position].description.strip()

    def get_all(self):
        return self.user_modules

UserModules = _UserModules()

try:
    #from . import example
    #from . import hello_one
    #from . import hello_two
    from . import ssh
    from . import other_modules
except Exception as e:
    print(e)
