from __future__ import annotations

import asyncio
from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING

import watchfiles

from alive.handlers import SSERequestHandler, StaticFileHandler, handle_reload_script
from alive.http_server import HTTPServer
from alive.protocols import AliveAction, Change, StrPath
from alive.responses import SSEMessage

if TYPE_CHECKING:
    from collections.abc import Awaitable


logger = getLogger(__name__)


class LiveServer(HTTPServer):
    html_injection = '<script defer src="/alive-reload.js"></script>'

    def __init__(
        self,
        root_dir: StrPath,
        host: str = "localhost",
        port: int = 8000,
    ) -> None:
        super().__init__(host, port)
        self.root_dir = Path(root_dir).resolve()
        self.watch_paths: dict[Path, AliveAction] = {}
        self.watch(root_dir, self._notify_file_changed)
        self.listeners: set[asyncio.Queue[SSEMessage]] = set()
        self.request_handlers = {
            "/alive-reload-sse": SSERequestHandler(self.listeners),
            "/alive-reload.js": handle_reload_script,
        }
        self.fallback_handler = StaticFileHandler(self.root_dir, self.html_injection)

    def watch(self, path: StrPath, action: AliveAction) -> None:
        self.watch_paths[Path(path).resolve()] = action

    async def watch_root(self) -> None:
        async for changes in watchfiles.awatch(*self.watch_paths):  # pyright: ignore[reportUnknownMemberType]
            await asyncio.gather(
                *(self._process_change(change, path) for change, path in changes)
            )

    async def serve(self) -> None:
        await asyncio.gather(super().serve(), self.watch_root())

    async def _process_change(
        self, watchfiles_change: watchfiles.main.Change, path_str: str
    ) -> None:
        path = Path(path_str)
        change = Change(watchfiles_change)
        if path.is_relative_to(self.root_dir):
            await self._notify_file_changed(
                change, f"/{path.relative_to(self.root_dir)}"
            )
        rel_path = path.relative_to(Path.cwd())
        logger.info("File %s %sd", rel_path, change.name.lower())

    async def _notify_file_changed(self, change: Change, path: StrPath) -> None:
        tasks: list[Awaitable[None]] = []
        for listener in self.listeners:
            path = str(path)
            if path.endswith("/index.html"):
                path = path[:-10]
            message = SSEMessage(
                event=change.name.lower(),
                payload=path,
            )
            tasks.append(listener.put(message))
        await asyncio.gather(*tasks)
