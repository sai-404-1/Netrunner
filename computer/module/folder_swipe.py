import shlex
import subprocess
from pathlib import Path

from config import *

from .executor_ssh import _ssh_common_options


def _build_ssh_cmd(host, port, remote_command):
    key_file = Path(KEY_PATH) / KEY_NAME
    return [
        "ssh",
        "-p", str(port),
        *_ssh_common_options(),
        "-i", str(key_file),
        host,
        remote_command,
    ]


def main(host, port="22", dir="$HOME"):
    # Do not shadow the builtin dir(); quote the user-provided path for the
    # remote shell to avoid command injection.
    target_dir = shlex.quote(dir)
    try:
        result = subprocess.run(
            _build_ssh_cmd(host, port, f"sudo rm -rf {target_dir}"),
            capture_output=True,
            text=True,
        )
        print(f"Deleting folder is {'success' if result.returncode == 0 else 'failure'}")
        result = subprocess.run(
            _build_ssh_cmd(host, port, f"sudo mkdir {target_dir} || sudo chown -R rmk:rmk {target_dir}"),
            capture_output=True,
            text=True,
        )
        print(f"Changing law is {'success' if result.returncode == 0 else 'failure'}")
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
