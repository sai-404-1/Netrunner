from config import *
import subprocess

def main(command: str = "uname -a"):
    cmd = ["sh", "-lc", f"{command}"]
    try:
        return str(subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            # errors="replace",
            # check=True,
        ).stdout.strip())
    except Exception as e:
        return f"Error: {e}"
    
class LocalComputer():
    def __init__(self):
        ...

    def local_executor(self, command="uname -a"):
        return main(command)