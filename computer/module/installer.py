import subprocess
import concurrent.futures
import time
from config import *

MAX_WORKERS = 10
RETRIES = 2
TIMEOUT = 15

packages = "blender"


def load_hosts():
    with open("ips.txt") as f:
        return [h.strip() for h in f if h.strip()]


def build_command(host):

    remote_cmd = (
        f"echo {PASSWORD} | sudo -S "
        f"DEBIAN_FRONTEND=noninteractive "
        f"apt-get install {packages} -y --fix-missing"
    )

    return [
        "ssh",
        "-o", "ConnectTimeout=3",
        "-i", f"./{KEY_PATH}/{KEY_NAME}",
        "-t",
        host,
        remote_cmd
    ]


def run_install(host):

    for attempt in range(1, RETRIES + 2):

        print(f"[{host}] attempt {attempt}")

        try:

            result = subprocess.run(
                build_command(host),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=TIMEOUT
            )

            if result.returncode == 0:

                print(f"[{host}] SUCCESS")
                return True

            else:

                print(f"[{host}] FAILED")
                print(result.stderr.decode())

        except subprocess.TimeoutExpired:

            print(f"[{host}] TIMEOUT")

        time.sleep(1)

    print(f"[{host}] GAVE UP")
    return False


def main():

    hosts = load_hosts()

    print(f"Hosts loaded: {len(hosts)}")

    results = []

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        future_map = {
            executor.submit(run_install, host): host
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


# if __name__ == "__main__":
    # main()