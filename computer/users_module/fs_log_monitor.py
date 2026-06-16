"""
NetRunner — демо-модуль мониторинга файловой системы

Собирает и логирует основные показатели файловой системы
на выбранных хостах: использование диска, inode,
крупнейшие каталоги и самые большие файлы.
"""

from computer import Computer
from computer.users_module import UserModules


class UserModule:
    slug = "fs_log_monitor"
    title = "Мониторинг файловой системы"
    description = (
        "Собирает информацию о файловой системе: "
        "использование диска, inode, "
        "крупнейшие каталоги и файлы."
    )

    def __init__(self):
        self.title = UserModule.title
        self.description = UserModule.description

    def _make_computer(self, context, host):
        to_computer = getattr(context, "to_computer", None)
        if callable(to_computer):
            try:
                return to_computer(host)
            except Exception:
                pass
        return Computer(
            host=f"{host.username}@{host.address}",
            port=str(host.port),
        )

    def _ssh_read(self, computer, command: str) -> str:
        try:
            result = computer.executor_ssh(command).strip()
        except Exception as e:
            return f"[ERROR] {e}"

        if not result:
            return ""

        if result.startswith("[ERROR]") or result.startswith("Error:"):
            return result

        return result

    def _clean_value(self, value: str) -> str:
        if not value:
            return ""
        if value.startswith("[ERROR]") or value.startswith("Error:"):
            return ""
        return value.strip()

    def _disk_usage(self, computer) -> str:
        cmd = "df -hP 2>/dev/null | awk 'NR==1 || $1 ~ \"^/dev/\" {print}'"
        return self._clean_value(self._ssh_read(computer, cmd))

    def _inode_usage(self, computer) -> str:
        cmd = "df -iP 2>/dev/null | awk 'NR==1 || $1 ~ \"^/dev/\" {print}'"
        return self._clean_value(self._ssh_read(computer, cmd))

    def _top_directories(self, computer, root_dir: str, top_n: int) -> str:
        if not root_dir or not root_dir.startswith("/"):
            root_dir = "/"
        safe_root = root_dir.replace("'", "'\\''")
        cmd = (
            f"find '{safe_root}' -maxdepth 1 -mindepth 1 -type d -exec du -sh {{}} + "
            f"2>/dev/null | sort -rh | head -n {int(top_n)}"
        )
        return self._clean_value(self._ssh_read(computer, cmd))

    def _largest_files(self, computer, root_dir: str, top_n: int) -> str:
        if not root_dir or not root_dir.startswith("/"):
            root_dir = "/"
        safe_root = root_dir.replace("'", "'\\''")
        cmd = (
            f"find '{safe_root}' -type f -size +1M -exec ls -lh {{}} + "
            f"2>/dev/null | awk '{{print $5, $9}}' | sort -rh | head -n {int(top_n)}"
        )
        return self._clean_value(self._ssh_read(computer, cmd))

    def _mount_summary(self, computer) -> str:
        cmd = "mount 2>/dev/null | awk '{print $1, $3, $5}' | head -n 20"
        return self._clean_value(self._ssh_read(computer, cmd))

    def run(self, context, targets, **kwargs):
        root_dir = str(kwargs.get("root_dir", "/")).strip() or "/"
        top_n = int(kwargs.get("top_n", 5))
        if top_n < 1:
            top_n = 5

        lines = []
        for host in targets:
            computer = self._make_computer(context, host)
            lines.append("=" * 60)
            lines.append(f"HOST: {host.name} ({host.username}@{host.address}:{host.port})")
            lines.append("=" * 60)

            disk = self._disk_usage(computer)
            if disk:
                lines.append("\n--- Использование дисков (df -h) ---")
                lines.append(disk)

            inodes = self._inode_usage(computer)
            if inodes:
                lines.append("\n--- Использование inode (df -i) ---")
                lines.append(inodes)

            top_dirs = self._top_directories(computer, root_dir, top_n)
            if top_dirs:
                lines.append(f"\n--- Крупнейшие каталоги в {root_dir} ---")
                lines.append(top_dirs)

            largest = self._largest_files(computer, root_dir, top_n)
            if largest:
                lines.append(f"\n--- Самые большие файлы в {root_dir} (>1M) ---")
                lines.append(largest)

            mounts = self._mount_summary(computer)
            if mounts:
                lines.append("\n--- Сводка монтирования ---")
                lines.append(mounts)

            lines.append("")

        return {
            "summary_text": "\n".join(lines).strip(),
        }


CustomModule = UserModule()
UserModules.add_update(CustomModule.title, CustomModule)
