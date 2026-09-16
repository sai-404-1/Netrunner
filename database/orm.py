from __future__ import annotations

import json
from pathlib import Path

from .connection import connect
from .repos import HostDefaultCredRepo
from .schema import create_schema
from .repos.host_repo import HostRepo
from .repos.ssh_key_repo import SSHKeyRepo
from .repos.group_repo import GroupRepo
from .repos.module_repo import ModuleRepo
from .repos.task_run_repo import TaskRunRepo
from .repos.inventory_repo import InventoryRepo
from .repos.schedule_repo import ScheduledTaskRepo
from .repos.report_repo import ReportRepo
from .repos.user_repo import UserRepo
from .repos.user_module_access_repo import UserModuleAccessRepo
from .repos.user_group_access_repo import UserGroupAccessRepo
from .repos.board_repo import BoardRepo
from .repos.uploaded_file_repo import UploadedFileRepo
from .repos.app_settings_repo import AppSettingsRepo
from .repos.trusted_device_repo import TrustedDeviceRepo
from .repos.host_agent_repo import HostAgentRepo
from .repos.host_event_repo import HostEventRepo
from .repos.system_log_repo import SystemLogRepo
from .repos.history_entry_repo import HistoryEntryRepo
from .repos.scenario_repo import ScenarioRepo, ScenarioFolderRepo, ScenarioStepRepo, ScenarioRunRepo, ScenarioStepRunRepo


class Database:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.conn = connect(self.db_path)
        create_schema(self.conn)

        self.ssh_keys = SSHKeyRepo(self.conn)
        self.hosts = HostRepo(self.conn)
        self.groups = GroupRepo(self.conn)
        self.modules = ModuleRepo(self.conn)
        self.task_runs = TaskRunRepo(self.conn)
        self.inventory = InventoryRepo(self.conn)
        self.scheduled = ScheduledTaskRepo(self.conn)
        self.reports = ReportRepo(self.conn)
        self.users = UserRepo(self.conn)
        self.user_module_access = UserModuleAccessRepo(self.conn)
        self.user_group_access = UserGroupAccessRepo(self.conn)
        self.boards = BoardRepo(self.conn)
        self.uploaded_files = UploadedFileRepo(self.conn)
        self.app_settings = AppSettingsRepo(self.conn)
        self.trusted_devices = TrustedDeviceRepo(self.conn)
        self.host_agents = HostAgentRepo(self.conn)
        self.host_events = HostEventRepo(self.conn)
        self.system_logs = SystemLogRepo(self.conn)
        self.history_entries = HistoryEntryRepo(self.conn)
        self.scenarios = ScenarioRepo(self.conn)
        self.scenario_folders = ScenarioFolderRepo(self.conn)
        self.scenario_steps = ScenarioStepRepo(self.conn)
        self.scenario_runs = ScenarioRunRepo(self.conn)
        self.scenario_step_runs = ScenarioStepRunRepo(self.conn)
        self.host_default_cred = HostDefaultCredRepo(self.conn)

        self._model_map = {
            'ssh_keys': self.ssh_keys,
            'hosts': self.hosts,
            'groups': self.groups,
            'modules': self.modules,
            'task_runs': self.task_runs,
            'inventory_snapshots': self.inventory,
            'scheduled_tasks': self.scheduled,
            'reports': self.reports,
            'users': self.users,
            'user_module_access': self.user_module_access,
            'user_group_access': self.user_group_access,
            'boards': self.boards,
            'uploaded_files': self.uploaded_files,
            'scenarios': self.scenarios,
            'scenario_folders': self.scenario_folders,
            'scenario_steps': self.scenario_steps,
            'scenario_runs': self.scenario_runs,
            'scenario_step_runs': self.scenario_step_runs,
            'trusted_devices': self.trusted_devices,
            'host_agents': self.host_agents,
            'host_events': self.host_events,
            'system_logs': self.system_logs,
            'history_entries': self.history_entries,
            'host_default_credentials': self.host_default_cred,
        }

    def model(self, name: str):
        try:
            return self._model_map[name]
        except KeyError as exc:
            raise KeyError(f'Unknown model: {name}') from exc

    def close(self) -> None:
        self.conn.close()

    def commit(self) -> None:
        self.conn.commit()

    def import_legacy_hosts_json(self, path, ssh_key_id=None):
        import json
        from pathlib import Path

        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))

        # Поддержка обоих legacy-форматов:
        # 1) ["user@ip", ...]
        # 2) {"ips": ["user@ip", ...]}
        if isinstance(data, list):
            entries = data
        elif isinstance(data, dict):
            if isinstance(data.get("ips"), list):
                entries = data["ips"]
            elif isinstance(data.get("hosts"), list):
                entries = data["hosts"]
            else:
                raise ValueError("hosts.json must contain a list or {'ips': [...]} format")
        else:
            raise ValueError("hosts.json must contain a list or {'ips': [...]} format")

        imported = 0

        for idx, entry in enumerate(entries, start=1):
            if not isinstance(entry, str):
                continue

            raw = entry.strip()
            if not raw:
                continue

            if "@" in raw:
                username, address = raw.split("@", 1)
            else:
                username, address = "root", raw

            name = f"host-{address.replace('.', '-')}"

            self.hosts.create(
                name=name,
                address=address,
                port=22,
                username=username,
                ssh_key_id=ssh_key_id,
                description="Imported from legacy hosts.json",
                is_active=1,
            )
            imported += 1

        return imported

def init_database(db_path: str | Path) -> Database:
    return Database(db_path)


def open_database(db_path: str | Path = 'data/netrunner.db') -> Database:
    return Database(db_path)
