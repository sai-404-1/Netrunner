from . import Modules


class UserModule:
    slug = "inventory_collect"

    def __init__(self):
        self.title = "Сбор инвентаризации"
        self.description = "Собирает краткую системную информацию по выбранным хостам."

    def exec(self):
        print("Этот модуль должен запускаться через систему задач.")

    def _make_computer(self, context, host):
        to_computer = getattr(context, "to_computer", None)
        if callable(to_computer):
            try:
                return to_computer(host)
            except Exception:
                pass

        from computer import Computer
        return Computer(
            host=f"{host.username}@{host.address}",
            port=str(host.port),
        )

    def _clean_ssh_output(self, result: str) -> str:
        try:
            result = (result or "").strip()
        except Exception as e:
            return f"[ERROR] {e}"

        if not result:
            return ""

        if result.startswith("[ERROR]") or result.startswith("Error:"):
            return result

        return result

    def _ssh_read(self, computer, command: str) -> str:
        try:
            result = computer.executor_ssh(command)
        except Exception as e:
            return f"[ERROR] {e}"
        return self._clean_ssh_output(result)

    async def _ssh_read_async(self, computer, command: str) -> str:
        try:
            result = await computer.async_executor_ssh(command)
        except Exception as e:
            return f"[ERROR] {e}"
        return self._clean_ssh_output(result)

    def _clean_value(self, value: str) -> str:
        if not value:
            return ""
        if value.startswith("[ERROR]") or value.startswith("Error:"):
            return ""
        return value.strip()

    def _read_hostname(self, computer) -> str:
        return self._clean_value(
            self._ssh_read(computer, 'hostname 2>/dev/null || uname -n 2>/dev/null')
        )

    async def _read_hostname_async(self, computer) -> str:
        return self._clean_value(
            await self._ssh_read_async(computer, 'hostname 2>/dev/null || uname -n 2>/dev/null')
        )

    def _read_os_name(self, computer) -> str:
        cmd = (
            'if [ -f /etc/os-release ]; then '
            'sed -n \'s/^PRETTY_NAME=//p\' /etc/os-release | head -n1 | tr -d \'"\' ; '
            'else '
            'uname -s 2>/dev/null; '
            'fi'
        )
        return self._clean_value(self._ssh_read(computer, cmd))

    async def _read_os_name_async(self, computer) -> str:
        cmd = (
            'if [ -f /etc/os-release ]; then '
            'sed -n \'s/^PRETTY_NAME=//p\' /etc/os-release | head -n1 | tr -d \'"\' ; '
            'else '
            'uname -s 2>/dev/null; '
            'fi'
        )
        return self._clean_value(await self._ssh_read_async(computer, cmd))

    def _read_kernel(self, computer) -> str:
        return self._clean_value(self._ssh_read(computer, 'uname -r 2>/dev/null || uname -a 2>/dev/null'))

    async def _read_kernel_async(self, computer) -> str:
        return self._clean_value(await self._ssh_read_async(computer, 'uname -r 2>/dev/null || uname -a 2>/dev/null'))

    def _read_ram_mb(self, computer) -> int:
        commands = [
            """awk '/^MemTotal:/ {print int($2 / 1024); exit}' /proc/meminfo 2>/dev/null""",
            """free -m 2>/dev/null | awk '/^Mem:/ {print $2; exit}'""",
            """sysctl -n hw.memsize 2>/dev/null | awk '{print int($1 / 1024 / 1024)}'""",
            """sysctl -n hw.physmem 2>/dev/null | awk '{print int($1 / 1024 / 1024)}'""",
        ]
        for cmd in commands:
            value = self._clean_value(self._ssh_read(computer, cmd))
            try:
                if value:
                    return int(float(value))
            except Exception:
                continue
        return 0

    async def _read_ram_mb_async(self, computer) -> int:
        commands = [
            """awk '/^MemTotal:/ {print int($2 / 1024); exit}' /proc/meminfo 2>/dev/null""",
            """free -m 2>/dev/null | awk '/^Mem:/ {print $2; exit}'""",
            """sysctl -n hw.memsize 2>/dev/null | awk '{print int($1 / 1024 / 1024)}'""",
            """sysctl -n hw.physmem 2>/dev/null | awk '{print int($1 / 1024 / 1024)}'""",
        ]
        for cmd in commands:
            value = self._clean_value(await self._ssh_read_async(computer, cmd))
            try:
                if value:
                    return int(float(value))
            except Exception:
                continue
        return 0

    def _read_disk_stats(self, computer):
        uname_s = self._clean_value(self._ssh_read(computer, 'uname -s 2>/dev/null'))

        if uname_s == "Darwin":
            cmd = """df -kP /private/var 2>/dev/null | awk 'NR==2 {printf "%d %d %d", int($2/1024/1024), int($3/1024/1024), int($4/1024/1024)}'"""
            value = self._clean_value(self._ssh_read(computer, cmd))
            parts = value.split()
            if len(parts) == 3:
                try:
                    total, used, free = map(float, parts)
                    return total, used, free, 1
                except Exception:
                    pass

        total_cmd = """df -kP 2>/dev/null | awk 'NR>1 && $1 ~ "^/dev/" && !seen[$1]++ {total+=$2; used+=$3; free+=$4; count+=1} END {printf "%d %d %d %d", int(total/1024/1024), int(used/1024/1024), int(free/1024/1024), count}'"""
        value = self._clean_value(self._ssh_read(computer, total_cmd))
        parts = value.split()
        if len(parts) == 4:
            try:
                total, used, free, count = parts
                return float(total), float(used), float(free), int(count)
            except Exception:
                pass

        root_cmd = """df -kP / 2>/dev/null | awk 'NR==2 {printf "%d %d %d", int($2/1024/1024), int($3/1024/1024), int($4/1024/1024)}'"""
        value = self._clean_value(self._ssh_read(computer, root_cmd))
        parts = value.split()
        if len(parts) == 3:
            try:
                total, used, free = map(float, parts)
                return total, used, free, 1
            except Exception:
                pass

        return 0.0, 0.0, 0.0, 0

    async def _read_disk_stats_async(self, computer):
        uname_s = self._clean_value(await self._ssh_read_async(computer, 'uname -s 2>/dev/null'))

        if uname_s == "Darwin":
            cmd = """df -kP /private/var 2>/dev/null | awk 'NR==2 {printf "%d %d %d", int($2/1024/1024), int($3/1024/1024), int($4/1024/1024)}'"""
            value = self._clean_value(await self._ssh_read_async(computer, cmd))
            parts = value.split()
            if len(parts) == 3:
                try:
                    total, used, free = map(float, parts)
                    return total, used, free, 1
                except Exception:
                    pass

        total_cmd = """df -kP 2>/dev/null | awk 'NR>1 && $1 ~ "^/dev/" && !seen[$1]++ {total+=$2; used+=$3; free+=$4; count+=1} END {printf "%d %d %d %d", int(total/1024/1024), int(used/1024/1024), int(free/1024/1024), count}'"""
        value = self._clean_value(await self._ssh_read_async(computer, total_cmd))
        parts = value.split()
        if len(parts) == 4:
            try:
                total, used, free, count = parts
                return float(total), float(used), float(free), int(count)
            except Exception:
                pass

        root_cmd = """df -kP / 2>/dev/null | awk 'NR==2 {printf "%d %d %d", int($2/1024/1024), int($3/1024/1024), int($4/1024/1024)}'"""
        value = self._clean_value(await self._ssh_read_async(computer, root_cmd))
        parts = value.split()
        if len(parts) == 3:
            try:
                total, used, free = map(float, parts)
                return total, used, free, 1
            except Exception:
                pass

        return 0.0, 0.0, 0.0, 0

    def _read_current_user(self, computer) -> str:
        return self._clean_value(self._ssh_read(computer, 'whoami 2>/dev/null'))

    async def _read_current_user_async(self, computer) -> str:
        return self._clean_value(await self._ssh_read_async(computer, 'whoami 2>/dev/null'))

    _PACKAGE_COUNT_CMD = (
        "("
        "dpkg -l 2>/dev/null | grep -c '^ii' || "
        "rpm -qa 2>/dev/null | wc -l || "
        "apk list --installed 2>/dev/null | wc -l || "
        "echo 0"
        ") 2>/dev/null | tail -1"
    )

    def _read_package_count(self, computer) -> int | None:
        value = self._clean_value(self._ssh_read(computer, self._PACKAGE_COUNT_CMD))
        try:
            n = int(value)
            return n if n > 0 else None
        except Exception:
            return None

    async def _read_package_count_async(self, computer) -> int | None:
        value = self._clean_value(await self._ssh_read_async(computer, self._PACKAGE_COUNT_CMD))
        try:
            n = int(value)
            return n if n > 0 else None
        except Exception:
            return None

    def _to_int(self, value, default=0):
        try:
            return int(str(value).strip())
        except Exception:
            return default

    def _to_float(self, value, default=0.0):
        try:
            return float(str(value).strip())
        except Exception:
            return default

    def run(self, context, targets, **kwargs):
        import json as _json
        inventory_items = []
        summary_lines = []

        for host in targets:
            computer = self._make_computer(context, host)

            hostname = self._read_hostname(computer)
            os_name = self._read_os_name(computer)
            kernel = self._read_kernel(computer)
            ram_mb = self._read_ram_mb(computer)
            disk_total_gb, disk_used_gb, disk_free_gb, disks_count = self._read_disk_stats(computer)
            current_user = self._read_current_user(computer)
            package_count = self._read_package_count(computer)

            raw = {
                "hostname": hostname,
                "os_name": os_name,
                "kernel": kernel,
                "ram_mb": ram_mb,
                "disk_total_gb": disk_total_gb,
                "disk_used_gb": disk_used_gb,
                "disk_free_gb": disk_free_gb,
                "disks_count": disks_count,
                "current_user": current_user,
                "package_count": package_count,
            }

            item = {
                "host_id": host.id,
                "hostname": hostname,
                "os_name": os_name,
                "kernel": kernel,
                "uptime_seconds": 0,
                "cpu_model": "",
                "ram_mb": self._to_int(ram_mb),
                "disks_total_gb": self._to_float(disk_total_gb),
                "disks_free_gb": self._to_float(disk_free_gb),
                "disks_count": self._to_int(disks_count),
                "current_user": current_user,
                "package_count": package_count,
                "raw_json": _json.dumps(raw, ensure_ascii=False, default=str),
            }
            inventory_items.append(item)

            summary_lines.append(
                f"{host.name} | {hostname} | {os_name} | kernel={kernel} | "
                f"ram={item['ram_mb']} MB | "
                f"disk_total={disk_total_gb:.1f} GB | "
                f"disk_used={disk_used_gb:.1f} GB | "
                f"disk_free={disk_free_gb:.1f} GB"
            )

        return {
            "summary_text": "\n".join(summary_lines),
            "inventory_items": inventory_items,
            "per_host_results": [
                {
                    "host_id": item["host_id"],
                    "name": summary_lines[i].split(" | ")[0],
                    "address": host.address,
                    "port": host.port,
                    "username": host.username,
                    "hostname": item["hostname"],
                    "os_name": item["os_name"],
                    "kernel": item["kernel"],
                    "ram_mb": item["ram_mb"],
                    "disks_total_gb": item["disks_total_gb"],
                    "disks_free_gb": item["disks_free_gb"],
                }
                for i, (item, host) in enumerate(zip(inventory_items, targets))
            ],
        }

    async def run_for_host(self, context, host, **kwargs):
        """Per-host async execution used by TaskRunner."""
        import json as _json
        computer = self._make_computer(context, host)

        hostname = await self._read_hostname_async(computer)
        os_name = await self._read_os_name_async(computer)
        kernel = await self._read_kernel_async(computer)
        ram_mb = await self._read_ram_mb_async(computer)
        disk_total_gb, disk_used_gb, disk_free_gb, disks_count = await self._read_disk_stats_async(computer)
        current_user = await self._read_current_user_async(computer)
        package_count = await self._read_package_count_async(computer)

        raw = {
            "hostname": hostname,
            "os_name": os_name,
            "kernel": kernel,
            "ram_mb": ram_mb,
            "disk_total_gb": disk_total_gb,
            "disk_used_gb": disk_used_gb,
            "disk_free_gb": disk_free_gb,
            "disks_count": disks_count,
            "current_user": current_user,
            "package_count": package_count,
        }

        item = {
            "host_id": host.id,
            "hostname": hostname,
            "os_name": os_name,
            "kernel": kernel,
            "uptime_seconds": 0,
            "cpu_model": "",
            "ram_mb": self._to_int(ram_mb),
            "disks_total_gb": self._to_float(disk_total_gb),
            "disks_free_gb": self._to_float(disk_free_gb),
            "disks_count": self._to_int(disks_count),
            "current_user": current_user,
            "package_count": package_count,
            "raw_json": _json.dumps(raw, ensure_ascii=False, default=str),
        }

        summary = (
            f"{host.name} | {hostname} | {os_name} | kernel={kernel} | "
            f"ram={item['ram_mb']} MB | "
            f"disk_total={disk_total_gb:.1f} GB | "
            f"disk_used={disk_used_gb:.1f} GB | "
            f"disk_free={disk_free_gb:.1f} GB"
        )

        return {
            "host_id": host.id,
            "name": host.name,
            "address": host.address,
            "port": host.port,
            "username": host.username,
            "output": summary,
            "inventory_item": item,
            "hostname": item["hostname"],
            "os_name": item["os_name"],
            "kernel": item["kernel"],
            "ram_mb": item["ram_mb"],
            "disks_total_gb": item["disks_total_gb"],
            "disks_free_gb": item["disks_free_gb"],
        }


CustomModule = UserModule()
Modules.add_update(CustomModule.title, CustomModule)
