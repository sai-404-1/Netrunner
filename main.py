import time
from os import system
from time import sleep
from threading import Thread
from random import randint
from config import HOSTS

from computer import Computer

targets = [
    ["java", [".tlauncher", ".minecraft", "Документ", "Загрузки", "PrismLauncher"]],
    ["steam", [".steam"]],
    ["winestart"],
    ["wine"]

]#, "winestart", "steam", "steamwebhelper"]
# forbidden = [".tlauncher", ".minecraft", "Документ", "Загрузки", "PrismLauncher"]

global killed
killed = {}

def get_target(host):
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
                            killed.update({host: N})
            except:
                ...
        # else:
            # print(ip, result)
            # b = a.executor_ssh(f'ps -ax | grep {result}')
            # print(b)
            # for i, process in enumerate(result):
                    # info = process[:100]
            # print(ip, pids, result if "steam" in result else ...)
                # for N in target[1]:
                    # if N in info:
                # print(f"({ip}) Найдена запрещёнка: ({pids[i]})")

global threads
threads = []
def create_thread():
    threads = []
    # system("clear")
    for kill in killed:
        print(f"{kill} — {killed.get(kill)}")
    for host in HOSTS: # 168
        th = Thread(target=get_target, args=(host, ))
        threads.append(th)
        th.start()

some_thread_life = []
tryed = 0

# create_thread()

if True:
    while True:
        # some_thread_life = []
        # for i, thread in enumerate(threads):
        #     # print(f"{i}:\t{thread.is_alive()}")
        #     some_thread_life.append(thread.is_alive())
        # if True in some_thread_life:
        #     continue
        # else:
        #     system("clear && echo All threads is dead")
        #     create_thread()
        #     ...
        # system("clear")
        # print(some_thread_life)
        tryed+=1
        print(f'{tryed}...')
        create_thread()
        sleep(5)

# print(f"Result of time: {sum(time_result)}")

# 2904