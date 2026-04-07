from os import system

def main():
    print("Попытка обновления кода... Все внесённые изменения будут стёрты")
    system("git pull origin main")