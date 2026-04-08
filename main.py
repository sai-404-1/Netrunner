from installer import updater
import computer.users_module as um
from threading import Thread

Thread(target=updater.get_update).start()

user_modules = [um.UserModules.get_all()]
proj_functions = [updater.get_update, updater.main]

# Парсинг модулей
module = [
        [module[m] for m in module]
            for module in user_modules
    ][0]
options = ""
for i, m in enumerate(module):
    options+=f"     {i+1}. {m.title}\n"

while True:
    try:
        print(f"Опции:\n{options}")
        user_input = int(input("Выберите цифру: "))
        try: module[user_input-1].exec()
        except Exception as e:
            print(e)
    except KeyboardInterrupt:
        print("\nЗавршение...\n")
        break