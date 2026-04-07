from computer import Computer
from config import HOSTS

def main(command):
    for host in HOSTS:
        result = Computer(host).executor_ssh(command)
        print(f"{host}:\t{result}")