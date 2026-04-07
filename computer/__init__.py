from .module.executor_ssh import main as executor_ssh
from .module.executor_scp import main as executor_scp
from .module.installer import main as installer # NOT WORK
from .module.hard_drive_check import main as hard_drive_check
from .module.ping import main as ping
from .module.folder_swipe import main as folder_swipe

class Computer():
    def __init__(
            self,
            host: str = "root@localhost",
            port: str = "22"
        ):
        self.host = host
        self.port = port

    def executor_ssh(self, command):
        return executor_ssh(host=self.host, port=self.port, command=command)
    
    def executor_scp(self, path_from, path_to):
        return executor_scp(host=self.host, port=self.port, path_from=path_from, path_to=path_to)
    
    def hard_drive_check(self):
        return hard_drive_check(host=self.host, port=self.port)
    
    def ping(self):
        return ping(ip=self.host.split("@")[1])
    
    def folder_swipe(self, dir):
        """Запрещает взаимодействие с папкой через присвоение её другому пользователю (chown -R)"""
        with open("./blacklist_program", "a") as f:
            f.write(f"\n{dir}")
        return folder_swipe(host=self.host, port=self.port, dir=dir)
    

from .module.local_executor import main as local_executor
class LocalComputer():
    def __init__(self):
        ...

    def local_executor(self, command="uname -a"):
        return local_executor(command)