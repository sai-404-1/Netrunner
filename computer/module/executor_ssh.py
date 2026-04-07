from config import *
import subprocess

def main(host, port = "22", command: str = "cat /etc/os-release | grep PRETTY_NAME"):
    # script = f"ssh -p {port} -o BatchMode=yes -o ConnectTimeout=1 -i ./{KEY_PATH}/{KEY_NAME} {host} '({command})'"
    cmd = [
        "ssh",
        "-p", str(port),
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=1",
        "-i", f"./{KEY_PATH}/{KEY_NAME}",
        host,
        "sh", "-lc", f"'({command})'",
    ]
    # print(cmd[-1])
    try:
        return str(subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            # errors="replace",
            # check=True,
        ).stdout.strip())
    except Exception as e:
        return f"Error: {e}"

# # TODO добавить валидацию
# with open("ips.txt") as f:
#     file = f.read()
#     hosts = file.split("\n")
#     print(f"{file}\n")
# for host in hosts:
#     print(host)
#     main(host, command="sudo setfacl -m u:student:--- /usr/bin/captain")