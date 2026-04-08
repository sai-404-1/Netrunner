from computer import LocalComputer

def main():
    print("Попытка обновления кода...")
    print(LocalComputer().local_executor("git pull origin main").strip())
    print("Перезапустите, чтобы применить изменения!")

def get_update(update=False):
    print("Проверяю git...")
    result = LocalComputer().local_executor("git fetch").strip()
    result = LocalComputer().local_executor(
        "git rev-list --count HEAD..@{u}"
    ).strip()
    
    if result == "0":
        if update == True: print("Кажется мы на последней версии...")
        else: ...
    else:
        print("\nЕсть обновления!")
        print("\nСообщение последнего коммита: ",
            LocalComputer().local_executor(
            "git --no-pager log -1 @{u} --pretty=%B"
        ))
        if update == True:
            if input("\nОбновиться? [y/1]").lower() in ["y", "1"]:
                main()
            else:
                print("Аборт")