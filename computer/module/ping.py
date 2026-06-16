import subprocess, platform

def main(ip, port="22", command: str = "cat /etc/os-release | grep PRETTY_NAME"):
    system = platform.system().lower()
    if system == "windows":
        # Windows: -n count, -w timeout_ms, -q quiet
        cmd = ["ping", "-n", "1", "-w", "5000", ip]
    else:
        # Linux/macOS: -c count, -W timeout_sec, -q quiet
        cmd = ["ping", "-c", "1", "-q", "-W", "50", ip]
    try:
        return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    except subprocess.CalledProcessError as e:
        return e.stdout or f"Host unreachable (exit {e.returncode})"
    except Exception as e:
        return f"Error: {e}"