from config import *
import subprocess

def main(ip, port = "22", command: str = "cat /etc/os-release | grep PRETTY_NAME"):
    script = f"""ping -c 1 -q -W 50 {ip}"""
    try:
        return str(subprocess.run(script, shell=True, capture_output=True, text=True, check=True).stdout)
    except Exception as e:
        return f"Error: {e}"