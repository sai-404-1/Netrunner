from threading import Thread

from computer import Computer
from random import randint
from config import HOSTS
from time import sleep
from . import UserModules

targets = [
    ["java", [".tlauncher", ".minecraft", "Документ", "Загрузки", "PrismLauncher"]],
    ["steam", [".steam"]],
]

def main(host):
    for target in targets:
        # print(f"Start cycle for {target}")
        # print("Results:")

        a = Computer(host)
        # Получение id процессов, которые соответствуют целевым
        pids = a.executor_ssh(f"for i in $(pgrep {target[0]}); do echo $i; done")
        # print(f"for i in $(pgrep {target[0]}); do echo $i; done")
        NEWLINE = "\n"
        pids = pids.split(NEWLINE)
        
        # Отправка запроса на вывод информации о конкретном процессе (тот, который запущен под целевым процессом)
        result = a.executor_ssh(f'for i in {" ".join(pids)}; do ps --format cmd -p $i; done')

        # Парсинг выводов и поиск запрещённых
        if len(target) > 1:
            try:
                result = result.split(NEWLINE)#.split(" ")[0].split("/")[3] # <–– path to parent folder
                result = [x for x in result if x != "CMD"]
                for i, process in enumerate(result):
                    info = process[:100].split(NEWLINE)[0].split("/")[1:]
                    for N in target[1]:
                        if N in info:
                            print(f"({host}) Найдена запрещёнка: {N} ({pids[i]})")
                            print(f"Попытка завершить процесс... ({pids[i]}){result}")
                            result = a.executor_ssh(f'sleep {randint(1, 5)}; sudo kill -9 {pids[i]}')
            except Exception as e:
                print(e)

class UserModule:
    def __init__(self):
        self.title = "Чёрные списки."
        self.description = """Пример использования: exec("Hello world!")"""

    def exec(self):
        print("Включаю глушилку...")
        try:
            while True:
                for host in HOSTS:
                    th = Thread(target=main, args=(host, ))
                    th.start()
                sleep(5)
        except KeyboardInterrupt:
            print("Остановлено...")

CustomModule = UserModule()

UserModules.add_update("blacklist", CustomModule)