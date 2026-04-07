from installer import updater
import computer.users_module as um
from threading import Thread
from config import HOSTS
from time import sleep

def create_thread():
    for host in HOSTS:
        th = Thread(target=um.blacklist.main, args=(host, ))
        th.start()

print("Опции:\n1: \"Глушилка\"\n2: Массовый SSH\n9: Обновиться")
user_input = input("Введите цифру:")

match int(user_input):
    case 1:
        print("Включаю глушилку...")
        while True:
            tryed+=1
            print(f'{tryed}...')
            create_thread()
            sleep(5)
    case 2:
        command = input("Ожидаю ввод команды: ")
        um.ssh.main(command)

    case 9:
        updater.main()