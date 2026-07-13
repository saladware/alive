from __future__ import annotations

from enum import IntEnum
from os import PathLike
from typing import Protocol, TypeAlias

StrPath: TypeAlias = str | PathLike[str]


class Change(IntEnum):
    CREATE = 1
    UPDATE = 2
    DELETE = 3


class AliveAction(Protocol):
    async def __call__(self, change: Change, path: StrPath, /) -> None: ...
