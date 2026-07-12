from __future__ import annotations

from collections.abc import Awaitable, Callable
from enum import IntEnum
from os import PathLike
from typing import NamedTuple, TypeAlias

StrPath: TypeAlias = str | PathLike[str]


class Change(IntEnum):
    CREATE = 1
    UPDATE = 2
    DELETE = 3


class FileChange(NamedTuple):
    change: Change
    path: StrPath


AliveAction: TypeAlias = Callable[[FileChange], Awaitable[None]]
