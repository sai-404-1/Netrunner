from computer import Computer
from config import HOSTS

def main(title="Test", message="message"):
    for host in HOSTS:
        result = Computer(host).executor_ssh(
            f"sudo -u user sh -lc notify-send {title} {message}"
        )
        print(f"{host}:\t{result}")