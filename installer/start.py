import os
from config import *
import subprocess
import json

# os.system(f"ssh-keygen -f ./{KEY_PATH}/{KEY_NAME} -N \"\"")

# something like handshake
def main():
    for host in HOSTS:
        print(f"Host IP now: {host}")
        script = f"""
            spawn ssh-copy-id -o StrictHostKeyChecking=no -o ConnectTimeout=1 -i ./{KEY_PATH}/{KEY_NAME}.pub {host}
            expect "password:"
            send "{PASSWORD}\\r"
            expect eof
        """
        try:
            print("="*30)
            result = subprocess.run(["expect", "-c", script])
            if result.returncode == 0:
                print(f"Successful for {host}")
        except Exception as e:
            print(f"Error was when key installing: {e}")

        print(f"Setting up password for RMK")

        # script = f"""
        #     spawn ssh -i {KEY_PATH}/{KEY_NAME} {host} sudo -S echo 'rmk ALL=(ALL) NOPASSWD:ALL' | sudo tee -a /etc/sudoers
        #     expect "password:"
        #     send "{PASSWORD}\\r"
        #     expect eof
        # """
        # try:
        #     print("="*30)
        #     result = subprocess.run(["expect", "-c", script])
        #     if result.returncode == 0:
        #         print(f"Successful for {host}")
        # except Exception as e:
        #     print(f"Error was when key installing: {e}")
    # now we should talk