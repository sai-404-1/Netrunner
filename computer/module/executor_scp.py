import subprocess
from pathlib import Path

KEY_NAME = "id_ed25519"
KEY_PATH = "keys"
try:
    from config import *
except ImportError:
    pass

from computer.module.executor_ssh import _ssh_common_options


def _build_scp_cmd(host, port, path_from, path_to):
    key_file = Path(KEY_PATH) / KEY_NAME
    return [
        "scp",
        "-P", str(port),
        *_ssh_common_options(),
        "-i", str(key_file),
        path_from,
        path_to,
    ]


def main(host, port="22", path_from=None, path_to=None):
    cmd = _build_scp_cmd(host, port, path_from, path_to)
    try:
        return subprocess.run(cmd, capture_output=True, text=True)
    except Exception as e:
        return f"Error was when key installing: {e}"
    return ""
