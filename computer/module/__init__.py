global _Modules
class _Modules:
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
    
Modules = _Modules()
from . import get_update
from . import availability_check
from . import inventory_collect
from . import apt_package_manager
from . import file_distribute
# try:
# except Exception as e:
#     print(e)
