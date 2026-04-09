from config import *
import subprocess
import shlex


def main(host, port="22", command: str = "uname -a"):
    remote_cmd = f"sh -lc {shlex.quote(command)}"

    cmd = [
        "ssh",
        "-p", str(port),
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=5",
        "-i", f"./{KEY_PATH}/{KEY_NAME}",
        host,
        remote_cmd,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()

        if result.returncode != 0:
            return (
                f"[ERROR] host={host}\n"
                f"returncode={result.returncode}\n"
                f"stderr:\n{stderr or '[empty]'}\n"
                f"stdout:\n{stdout or '[empty]'}"
            )

        if stderr:
            return f"{stdout}\n[stderr]\n{stderr}".strip()

        return stdout or "[пустой stdout]"

    except Exception as e:
        return f"Error: {e}"