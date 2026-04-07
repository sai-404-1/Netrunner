from installer import updater
import computer.users_module as um
from threading import Thread
from config import HOSTS
from time import sleep

def create_thread():
    for host in HOSTS:
        th = Thread(target=um.blacklist.main, args=(host, ))
        th.start()

print("Опции:\n1: \"Глушилка\"\n2: Массовый SSH\n9: Обновиться\n")
user_input = input("Введите цифру: ")

match int(user_input):
    case 1:
        print("Включаю глушилку...")
        while True:
            create_thread()
            sleep(5)
    case 2:
        command = input("Ожидаю ввод команды: ")
        um.ssh.main(command)

    case 9:
        updater.main()