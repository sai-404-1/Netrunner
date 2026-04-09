from threading import Thread

from computer import Computer
from random import randint
from config import HOSTS
from time import sleep
from . import UserModules

targets = [
    ["java", [".tlauncher", ".minecraft", "PrismLauncher"]],
    ["steam", [".steam", "share", ".var"]],
]

def main(host):
    a = Computer(host)
    for target_name, blacklist in targets:
        cmd = (
            f'for pid in $(pgrep -x {target_name} 2>/dev/null); do '
            'ps -p "$pid" -o pid= -o args=; '
            'done'
        )
        result = a.executor_ssh(cmd)
        if not result:
            continue

        lines = [line.strip() for line in result.splitlines() if line.strip()]
        for line in lines:
            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                continue

            pid, args = parts
            for banned in blacklist:
                if banned in args:
                    print(f"({host}) Найдена запрещёнка: {banned} в процессе {target_name} PID={pid}")
                    print(f"({host}) Команда: {args}")
                    delay = randint(1, 5)
                    a.executor_ssh(f'sleep {delay}; sudo kill -9 {pid} 2>/dev/null || true')
                    a.executor_ssh(f'sudo -u student XDG_RUNTIME_DIR=/run/user/1001 pactl set-sink-volume @DEFAULT_SINK@ 100%')
                    a.executor_ssh(f'sudo -u student XDG_RUNTIME_DIR=/run/user/1001  ffplay -nodisp -autoexit "http://180.160.1.145:8091/dexter-meme.mp3"')
                    break


class UserModule:
    def __init__(self):
        self.title = "Чёрные списки."
        self.description = "Ищет запрещённые приложения внутри целевых процессов и завершает их."

    def exec(self):
        print("Включаю глушилку...")
        try:
            while True:
                for host in HOSTS:
                    th = Thread(target=main, args=(host,))
                    th.start()
                sleep(5)
        except KeyboardInterrupt:
            print("Остановлено...")


CustomModule = UserModule()

UserModules.add_update("blacklist", CustomModule)