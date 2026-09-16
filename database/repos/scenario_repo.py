from __future__ import annotations

from .base import BaseRepository
from database.models.scenario import Scenario, ScenarioFolder, ScenarioStep, ScenarioRun, ScenarioStepRun


class ScenarioFolderRepo(BaseRepository):
    model_cls = ScenarioFolder
    table_name = 'scenario_folders'

    def all_sorted(self):
        """Папки по алфавиту. Сортировка в Python: SQLite COLLATE NOCASE
        сворачивает только латиницу, а имена папок здесь русские."""
        return sorted(self.all(), key=lambda f: (f.name or "").casefold())

    def by_name(self, name: str):
        """Поиск по имени без учёта регистра (сравнение в Python — см. all_sorted)."""
        needle = (name or "").strip().casefold()
        for folder in self.all():
            if (folder.name or "").casefold() == needle:
                return folder
        return None


class ScenarioRepo(BaseRepository):
    model_cls = Scenario
    table_name = 'scenarios'

    def clear_folder(self, folder_id: int) -> None:
        """Выносит сценарии удалённой папки в корень (ON DELETE SET NULL работает
        только при включённых FK-прагмах, поэтому чистим явно)."""
        self.conn.execute(
            f'UPDATE {self.table_name} SET folder_id = NULL WHERE folder_id = ?',
            (folder_id,),
        )
        self.conn.commit()


class ScenarioStepRepo(BaseRepository):
    model_cls = ScenarioStep
    table_name = 'scenario_steps'

    def by_scenario(self, scenario_id: int):
        rows = self._fetchall(
            f'SELECT * FROM {self.table_name} WHERE scenario_id = ? ORDER BY step_order',
            (scenario_id,),
        )
        return [self._row_to_model(row) for row in rows]

    def update_one(self, scenario_id: int, config_json: str):
        return self.update(scenario_id, config_json=config_json)

    def max_order(self, scenario_id: int) -> int:
        row = self._fetchone(
            f'SELECT COALESCE(MAX(step_order), 0) FROM {self.table_name} WHERE scenario_id = ?',
            (scenario_id,),
        )
        return row[0] if row else 0


class ScenarioRunRepo(BaseRepository):
    model_cls = ScenarioRun
    table_name = 'scenario_runs'

    def by_scenario(self, scenario_id: int):
        rows = self._fetchall(
            f'SELECT * FROM {self.table_name} WHERE scenario_id = ? ORDER BY id DESC',
            (scenario_id,),
        )
        return [self._row_to_model(row) for row in rows]

    def start(self, scenario_id: int, target_type: str, target_id: int, trigger_type: str = 'manual'):
        from database.repos.base import utcnow_iso
        now = utcnow_iso()
        return self.create(scenario_id=scenario_id, target_type=target_type, target_id=target_id, status='running', started_at=now, trigger_type=trigger_type)

    def finish(self, run_id: int, status: str):
        from database.repos.base import utcnow_iso
        return self.update(run_id, status=status, finished_at=utcnow_iso())


class ScenarioStepRunRepo(BaseRepository):
    model_cls = ScenarioStepRun
    table_name = 'scenario_step_runs'

    def by_run(self, scenario_run_id: int):
        rows = self._fetchall(f'SELECT * FROM {self.table_name} WHERE scenario_run_id = ? ORDER BY id', (scenario_run_id,))
        return [self._row_to_model(row) for row in rows]

    def by_run_and_host(self, scenario_run_id: int, host_id: int):
        rows = self._fetchall(f'SELECT * FROM {self.table_name} WHERE scenario_run_id = ? AND host_id = ? ORDER BY id', (scenario_run_id, host_id))
        return [self._row_to_model(row) for row in rows]

    def start_step(self, scenario_run_id: int, step_id: int, host_id: int, module_id: int):
        from database.repos.base import utcnow_iso
        return self.create(scenario_run_id=scenario_run_id, step_id=step_id, host_id=host_id, module_id=module_id, status='running', started_at=utcnow_iso())

    def finish_step(self, step_run_id: int, status: str, output_text: str = '', error_text: str = '', exit_code: int = 0):
        from database.repos.base import utcnow_iso
        return self.update(step_run_id, status=status, output_text=output_text, error_text=error_text, exit_code=exit_code, finished_at=utcnow_iso())
