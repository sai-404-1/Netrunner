from installer import updater
import computer.users_module as um
from threading import Thread
from config import HOSTS
from time import sleep
from os import system

def create_thread():
    for host in HOSTS:
        th = Thread(target=um.blacklist.main, args=(host, ))
        th.start()

Thread(target=updater.get_update).start()

proj_functions = [updater.get_update, updater.main]
while True:
    print("Опции:\n1: \"Глушилка\"\n2: Массовый SSH\n\n9: Обновиться\n")
    user_input = int(input("Введите цифру: "))
    match user_input:
        case 1:
            print("Включаю глушилку...")
            try:
                while True:
                    create_thread()
                    sleep(5)
            except KeyboardInterrupt:
                print("Остановлено...")
                continue
        case 2:
            try:
                command = input("Ожидаю ввод команды: ")
                um.ssh.main(command)
            except KeyboardInterrupt:
                print("Остановлено...")
                continue
        # Под остальное...
        case _:
            try: proj_functions[user_input-8]()
            except: print("Такого варианта нет!")