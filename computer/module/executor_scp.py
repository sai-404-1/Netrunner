from config import *
import subprocess

def main(host, port = "22", path_from=None, path_to=None):
    # script = f"""
    #     spawn ssh -p {port} -o ConnectTimeout=1 -o StrictHostKeyChecking=no -o ConnectionAttempts=1 -i ./{KEY_PATH}/{KEY_NAME} {host} {command}
    #     expect "password:"
    #     send "{PASSWORD}\\r"
    #     expect eof
    # """
    script = f"""scp -P {port} -o BatchMode=yes -o ConnectTimeout=1 -i ./{KEY_PATH}/{KEY_NAME} {path_from} {path_to}"""
    print(script)
    try:
        return subprocess.run(script, shell=True)
    except Exception as e:
        return f"Error was when key installing: {e}"
    return ""


# # TODO добавить валидацию
# with open("ips.txt") as f:
#     file = f.read()
#     hosts = file.split("\n")
#     print(f"{file}\n")
# for host in hosts:
#     print(host)
#     main(host, command="sudo setfacl -m u:student:--- /usr/bin/captain")