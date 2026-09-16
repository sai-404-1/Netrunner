from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from .base import BaseModel


@dataclass(slots=True)
class ScenarioFolder(BaseModel):
    __table__: ClassVar[str] = 'scenario_folders'
    id: int | None = None
    name: str = ''
    created_at: str = ''
    updated_at: str = ''


@dataclass(slots=True)
class Scenario(BaseModel):
    __table__: ClassVar[str] = 'scenarios'
    id: int | None = None
    name: str = ''
    description: str | None = None
    target_type: str = 'group'
    target_id: int | None = None
    folder_id: int | None = None
    created_at: str = ''
    updated_at: str = ''


@dataclass(slots=True)
class ScenarioStep(BaseModel):
    __table__: ClassVar[str] = 'scenario_steps'
    id: int | None = None
    scenario_id: int = 0
    module_id: int = 0
    step_order: int = 0
    step_name: str = ''
    config_json: str = '{}'
    depends_on_step_id: int | None = None
    on_failure: str = 'stop'
    retry_count: int = 0
    created_at: str = ''


@dataclass(slots=True)
class ScenarioRun(BaseModel):
    __table__: ClassVar[str] = 'scenario_runs'
    id: int | None = None
    scenario_id: int = 0
    target_type: str = ''
    target_id: int = 0
    status: str = 'pending'
    started_at: str | None = None
    finished_at: str | None = None
    trigger_type: str = 'manual'


@dataclass(slots=True)
class ScenarioStepRun(BaseModel):
    __table__: ClassVar[str] = 'scenario_step_runs'
    id: int | None = None
    scenario_run_id: int = 0
    step_id: int = 0
    host_id: int = 0
    module_id: int = 0
    status: str = 'pending'
    output_text: str | None = None
    error_text: str | None = None
    exit_code: int | None = None
    started_at: str | None = None
    finished_at: str | None = None
