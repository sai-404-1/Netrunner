from computer import Computer
from config import HOSTS


def main(title="Test", message="message", username="rmk"):
    for host in HOSTS:
        result = Computer(host).executor_ssh(
            f"sudo -u {username} DISPLAY=:0 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u {username})/bus "
            f"notify-send '{title}' '{message}'"
        )
        print(f"{host}:\t{result}")
