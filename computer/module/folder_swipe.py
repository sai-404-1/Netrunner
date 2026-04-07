from config import *
import subprocess

def main(host, port = "22", dir = "$HOME"):
    try:
        result = subprocess.run(f"ssh -p {port} -o BatchMode=yes -o ConnectTimeout=1 -i ./{KEY_PATH}/{KEY_NAME} {host} sudo rm -rf {dir}", shell=True)
        print(f"Deleting folder is {'success' if result.stderr == 0 else 'failure'}")
        result = subprocess.run(f"ssh -p {port} -o BatchMode=yes -o ConnectTimeout=1 -i ./{KEY_PATH}/{KEY_NAME} {host} sudo mkdir {dir} || sudo chown -R rmk:rmk {dir}", shell=True)
        print(f"Changing law is {'success' if result.stderr == 0 else 'failure'}")
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