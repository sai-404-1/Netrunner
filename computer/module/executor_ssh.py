import asyncio
import shlex
from pathlib import Path

# Secure defaults. A deployment config module may override these.
KEY_NAME = "id_ed25519"
KEY_PATH = "keys"
SSH_STRICT_HOST_KEY_CHECKING = "yes"
SSH_KNOWN_HOSTS_FILE = None
SSH_CHECK_HOST_IP = None
try:
    from config import *
except ImportError:
    pass


def _ssh_common_options():
    """Return common SSH options with strict host-key verification.

    The default policy is StrictHostKeyChecking=yes. If the deployment needs
    to accept unknown keys on first use, the operator can set
    SSH_STRICT_HOST_KEY_CHECKING=accept-new and SSH_KNOWN_HOSTS_FILE to a
    writable known-hosts file. The code never silently trusts any host.
    """
    strict = SSH_STRICT_HOST_KEY_CHECKING
    known_hosts = SSH_KNOWN_HOSTS_FILE
    check_ip = SSH_CHECK_HOST_IP
    options = [
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=15",
        "-o", f"StrictHostKeyChecking={strict}",
        "-o", "LogLevel=ERROR",
    ]
    if known_hosts is not None:
        options.extend(
            ["-o", f"UserKnownHostsFile={str(Path(known_hosts).expanduser())}"]
        )
    if check_ip is not None:
        options.extend(["-o", f"CheckHostIP={check_ip}"])
    return options


def _build_ssh_cmd(host, port, command, key_path=None):
    remote_cmd = f"sh -lc {shlex.quote(command)}"
    key_file = Path(key_path) if key_path else Path(KEY_PATH) / KEY_NAME

    return [
        "ssh",
        "-p", str(port),
        *_ssh_common_options(),
        "-i", str(key_file),
        host,
        remote_cmd,
    ]


def _format_result(host, returncode, stdout, stderr):
    if returncode != 0:
        return (
            f"[ERROR] host={host}\n"
            f"returncode={returncode}\n"
            f"stderr:\n{stderr or '[empty]'}\n"
            f"stdout:\n{stdout or '[empty]'}"
        )

    if stderr:
        return f"{stdout}\n[stderr]\n{stderr}".strip()

    return stdout or "[пустой stdout]"


def main(host, port="22", command: str = "uname -a", key_path=None):
    import subprocess

    cmd = _build_ssh_cmd(host, port, command, key_path=key_path)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()

        return _format_result(host, result.returncode, stdout, stderr)

    except Exception as e:
        return f"Error: {e}"


async def async_main(host, port="22", command: str = "uname -a", key_path=None):
    """Async version of SSH command execution.

    Runs the SSH subprocess via asyncio and supports cancellation:
    cancelling the surrounding asyncio.Task terminates the subprocess.
    """
    cmd = _build_ssh_cmd(host, port, command, key_path=key_path)

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except Exception as e:
        return f"Error: {e}"

    # TODO добавить отслеживание запущенных ssh процессов с возможностью их завершения
    SSH_COMMAND_TIMEOUT = 600  # seconds; covers the remote command execution after connect

    async def _communicate():
        return await proc.communicate()

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(_communicate(), timeout=SSH_COMMAND_TIMEOUT)
    except asyncio.TimeoutError:
        proc.kill()
        try:
            await asyncio.wait_for(proc.wait(), timeout=2)
        except asyncio.TimeoutError:
            pass
        return f"[ERROR] host={host}\nSSH command timed out after {SSH_COMMAND_TIMEOUT}s"
    except asyncio.CancelledError:
        proc.kill()
        try:
            await asyncio.wait_for(proc.wait(), timeout=2)
        except asyncio.TimeoutError:
            pass
        raise

    stdout = (stdout_bytes.decode("utf-8", errors="replace") or "").strip()
    stderr = (stderr_bytes.decode("utf-8", errors="replace") or "").strip()

    return _format_result(host, proc.returncode, stdout, stderr)
