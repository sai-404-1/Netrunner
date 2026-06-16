import concurrent.futures
import os
import shlex
import subprocess
import time
from pathlib import Path

from config import *

from computer.module.executor_ssh import _ssh_common_options

MAX_WORKERS = 10
RETRIES = 2
TIMEOUT = 15


def load_hosts():
    with open("ips.txt") as f:
        return [h.strip() for h in f if h.strip()]


def build_command(host, packages):
    password = os.environ.get("INSTALL_SUDO_PASSWORD")
    # Quote each package name so the remote shell receives them as separate
    # arguments, preventing command injection through the package list.
    packages_list = " ".join(shlex.quote(p) for p in packages.split())
    remote_cmd = (
        f"DEBIAN_FRONTEND=noninteractive sudo -S "
        f"apt-get install {packages_list} -y --fix-missing"
    )
    key_file = Path(KEY_PATH) / KEY_NAME
    cmd = [
        "ssh",
        "-o", "ConnectTimeout=3",
        *_ssh_common_options(),
        "-i", str(key_file),
        host,
        remote_cmd,
    ]
    # Pass the password to sudo via stdin; never embed it in the command string.
    if password:
        return cmd, password.encode("utf-8")
    return cmd, None


def run_install(host, packages):
    for attempt in range(1, RETRIES + 2):
        print(f"[{host}] attempt {attempt}")
        try:
            cmd, password_input = build_command(host, packages)
            kwargs = {}
            if password_input is not None:
                kwargs["input"] = password_input
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=TIMEOUT,
                **kwargs,
            )
            if result.returncode == 0:
                print(f"[{host}] SUCCESS")
                return True
            else:
                print(f"[{host}] FAILED")
                print(result.stderr.decode("utf-8", errors="replace"))
        except subprocess.TimeoutExpired:
            print(f"[{host}] TIMEOUT")
        time.sleep(1)
    print(f"[{host}] GAVE UP")
    return False


def main():
    packages = os.environ.get("INSTALL_PACKAGES")
    if not packages:
        raise RuntimeError("INSTALL_PACKAGES environment variable is not set")

    hosts = load_hosts()
    print(f"Hosts loaded: {len(hosts)}")
    results = []
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:
        future_map = {
            executor.submit(run_install, host, packages): host
            for host in hosts
        }
        for future in concurrent.futures.as_completed(future_map):
            host = future_map[future]
            try:
                result = future.result()
                results.append((host, result))
            except Exception as e:
                print(f"[{host}] ERROR: {e}")
                results.append((host, False))
    print("\nSUMMARY")
    for host, status in results:
        if status:
            print(f"{host} OK")
        else:
            print(f"{host} FAIL")
