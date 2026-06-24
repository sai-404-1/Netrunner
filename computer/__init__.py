from .module.executor_ssh import main as executor_ssh
from .module.executor_ssh import async_main as async_executor_ssh
from .module.executor_scp import main as executor_scp
from .module.hard_drive_check import main as hard_drive_check
from .module.ping import main as ping
from .module.folder_swipe import main as folder_swipe

class Computer():
    def __init__(
            self,
            host: str = "root@localhost",
            port: str = "22",
            key_path: str | None = None,
        ):
        self.host = host
        self.port = port
        self.key_path = key_path

    def executor_ssh(self, command):
        return executor_ssh(host=self.host, port=self.port, command=command, key_path=self.key_path)

    async def async_executor_ssh(self, command):
        return await async_executor_ssh(host=self.host, port=self.port, command=command, key_path=self.key_path)

    def executor_scp(self, path_from, path_to):
        return executor_scp(host=self.host, port=self.port, path_from=path_from, path_to=path_to)
    
    def hard_drive_check(self):
        return hard_drive_check(host=self.host, port=self.port)
    
    def ping(self):
        return ping(ip=self.host.split("@")[1])
    
    def folder_swipe(self, dir):
        """Запрещает взаимодействие с папкой через присвоение её другому пользователю (chown -R)"""
        return folder_swipe(host=self.host, port=self.port, dir=dir, key_path=self.key_path)
