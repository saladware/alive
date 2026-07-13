"""Live-reloading server orchestrator that monitors file changes and handles routing."""

from __future__ import annotations

import asyncio
from enum import IntEnum
from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import watchfiles

from alive.handlers import SSERequestHandler, StaticFileHandler, handle_reload_script
from alive.http_server import HTTPServer
from alive.responses import SSEMessage

if TYPE_CHECKING:
    from collections.abc import Awaitable
    from os import PathLike


logger = getLogger(__name__)


class LiveServer(HTTPServer):
    """
    An HTTP server with live-reloading capabilities.

    Extends the base HTTPServer to monitor file system changes and broadcast
    Server-Sent Events (SSE) to connected clients for automatic browser reloading.

    Attributes:
        html_injection: The JavaScript snippet injected into HTML responses
            to establish the SSE connection for live reloading.

    """

    html_injection = '<script defer src="/alive-reload.js"></script>'

    def __init__(
        self,
        root_dir: str | PathLike[str],
        host: str = "localhost",
        port: int = 8000,
    ) -> None:
        """
        Initialize the live reload server.

        Args:
            root_dir: The root directory to serve files from and monitor.
            host: The hostname or IP address to bind the server to. Defaults to
                "localhost".
            port: The port number to listen on. Defaults to 8000.

        """
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

    def watch(self, path: str | PathLike[str], action: AliveAction) -> None:
        """
        Register a path to be monitored with a specific callback action.

        Args:
            path: The file system path to watch.
            action: An asynchronous callable to execute when a change is detected.

        """
        self.watch_paths[Path(path).resolve()] = action

    async def watch_root(self) -> None:
        """Asynchronously monitors all registered paths for changes."""
        async for changes in watchfiles.awatch(*self.watch_paths):  # pyright: ignore[reportUnknownMemberType]
            await asyncio.gather(
                *(self._process_change(change, path) for change, path in changes),
            )

    async def serve(self) -> None:
        """
        Start the server and begins watching for file changes concurrently.

        This method runs the underlying HTTP server loop and the file watcher
        background task together using `asyncio.gather`.

        """
        await asyncio.gather(super().serve(), self.watch_root())

    async def _process_change(
        self,
        watchfiles_change: watchfiles.main.Change,
        path_str: str,
    ) -> None:
        path = Path(path_str)
        change = Change(watchfiles_change)

        rel_path = (
            path.relative_to(Path.cwd()) if path.is_relative_to(Path.cwd()) else path
        )
        logger.info("File %s %sd", rel_path, change.name.lower())

        matched_action: AliveAction | None = None
        best_match_len = -1

        for watch_path, action in self.watch_paths.items():
            if path == watch_path or path.is_relative_to(watch_path):
                match_len = len(watch_path.parts)
                if match_len > best_match_len:
                    best_match_len = match_len
                    matched_action = action

        if matched_action is not None:
            await matched_action(change, path)

    async def _notify_file_changed(
        self,
        change: Change,
        path: str | PathLike[str],
    ) -> None:
        url_path = f"/{Path(path).relative_to(self.root_dir)}"
        tasks: list[Awaitable[None]] = []
        for listener in self.listeners:
            if url_path.endswith("/index.html"):
                url_path = url_path[:-10]
            message = SSEMessage(
                event=change.name.lower(),
                payload=url_path,
            )
            tasks.append(listener.put(message))
        await asyncio.gather(*tasks)


class Change(IntEnum):
    """
    Enumeration of file system change types.

    Attributes:
        CREATE: Indicates a new file or directory was created.
        UPDATE: Indicates an existing file or directory was modified.
        DELETE: Indicates a file or directory was removed.

    """

    CREATE = 1
    UPDATE = 2
    DELETE = 3


class AliveAction(Protocol):
    """
    Protocol defining the structural type for file change event handlers.

    Classes or callables implementing this protocol must be asynchronous and accept
    the specific change type and target path as positional-only arguments.
    """

    async def __call__(self, change: Change, path: str | PathLike[str], /) -> None:
        """
        Asynchronously handle a file system change event.

        Args:
            change: The type of file change that occurred (CREATE, UPDATE, or DELETE).
            path: The system path where the change took place.

        """
