import shlex
import subprocess
from pathlib import Path

from config import *

from .executor_ssh import _ssh_common_options


def _build_ssh_cmd(host, port, remote_command, key_path=None):
    key_file = Path(key_path) if key_path else Path(KEY_PATH) / KEY_NAME
    return [
        "ssh",
        "-p", str(port),
        *_ssh_common_options(),
        "-i", str(key_file),
        host,
        remote_command,
    ]


def main(host, port="22", dir="$HOME", key_path=None):
    target_dir = shlex.quote(dir)
    try:
        result = subprocess.run(
            _build_ssh_cmd(host, port, f"sudo rm -rf {target_dir}", key_path=key_path),
            capture_output=True,
            text=True,
            timeout=30,
        )
        print(f"Deleting folder is {'success' if result.returncode == 0 else 'failure'}")
        # Use $(id -un) to get the current remote user instead of a hardcoded account.
        result = subprocess.run(
            _build_ssh_cmd(host, port, f"sudo mkdir -p {target_dir} && sudo chown -R $(id -un):$(id -gn) {target_dir}", key_path=key_path),
            capture_output=True,
            text=True,
            timeout=30,
        )
        print(f"Changing ownership is {'success' if result.returncode == 0 else 'failure'}")
    except subprocess.TimeoutExpired:
        print("Error: SSH command timed out")
    except Exception as e:
        print(f"Error was when key installing: {e}")


if __name__ == "__main__":
    with open("ips.txt") as f:
        hosts = [h.strip() for h in f if h.strip()]
    for h in hosts:
        main(h)
