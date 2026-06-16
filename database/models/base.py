from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any, ClassVar


@dataclass(slots=True)
class BaseModel:
    __table__: ClassVar[str] = ''
    __pk__: ClassVar[str] = 'id'

    @classmethod
    def columns(cls, include_pk: bool = True) -> list[str]:
        names = [f.name for f in fields(cls)]
        if include_pk:
            return names
        return [name for name in names if name != cls.__pk__]

    @classmethod
    def from_row(cls, row: Any):
        if row is None:
            return None
        data = {column: row[column] for column in cls.columns() if column in row.keys()}
        return cls(**data)

    def to_record(self, include_pk: bool = False) -> dict[str, Any]:
        data = asdict(self)
        if not include_pk:
            data.pop(self.__pk__, None)
        return data
