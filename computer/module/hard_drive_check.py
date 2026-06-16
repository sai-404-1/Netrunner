import subprocess
from pathlib import Path

from config import *

from .executor_ssh import _ssh_common_options


def main(host, port="22"):
    key_file = Path(KEY_PATH) / KEY_NAME
    cmd = [
        "ssh",
        "-p", str(port),
        *_ssh_common_options(),
        "-i", str(key_file),
        host,
        "df -h",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return f"[ERROR] host={host}\nreturncode={result.returncode}\nstderr:\n{result.stderr or '[empty]'}"
        return result.stdout
    except Exception as e:
        return f"Error: {e}"


if __name__ == "__main__":
    # TODO добавить валидацию
    with open("ips.txt") as f:
        file = f.read()
        hosts = file.split("\n")
        print(f"{file}\n")
    for host in hosts:
        main(host)
