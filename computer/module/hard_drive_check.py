from config import *
import subprocess

def main(host, port = "22"):
    try:
        subprocess.run(f"ssh -p {port} -o BatchMode=yes -o ConnectTimeout=1 -i ./{KEY_PATH}/{KEY_NAME} {host} df -h", shell=True)
    except Exception as e:
        print(f"Error was when key installing: {e}")

if __name__ == "__main__":
    # TODO добавить валидацию
    with open("ips.txt") as f:
        file = f.read()
        hosts = file.split("\n")
        print(f"{file}\n")
    for host in hosts:
        main(host)