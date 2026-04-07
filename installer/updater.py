from os import system
from time import sleep
from computer import LocalComputer

def main():
    print("Попытка обновления кода... Все внесённые изменения будут стёрты")
    print(LocalComputer().local_executor("git pull origin main").strip())

def get_update():
    print("Проверяю git...")
    result = LocalComputer().local_executor("git fetch").strip()
    result = LocalComputer().local_executor(
        "git rev-list --count HEAD..@{u}"
    ).strip()
    
    if result == "0":
        # print("Кажется мы на последней версии...")
        ...
    else:
        print("Есть обновления!")
        print("\nСообщение последнего коммита: ",
            LocalComputer().local_executor(
            "git --no-pager log -1 @{u} --pretty=%B"
        ))
        # if input("\nОбновиться? [y/1]").lower() in ["y", "1"]:
        #     main()
        # else:
        #     print("Аборт")