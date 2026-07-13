"""Handlers for serving static client-side live-reload scripts."""

import asyncio
import os
from http import HTTPStatus
from pathlib import Path

from alive.request import Request
from alive.responses import EmptyResponse, FileResponse, Response


async def handle_reload_script(request: Request) -> Response:
    """
    Asynchronously serves the live-reload JavaScript client file.

    This handler manages client-side caching by checking the file's modification
    time and utilizing the `ETag` and `If-None-Match` HTTP headers. If the file
    has not changed, it efficiently returns a `304 Not Modified` response.

    Args:
        request: The incoming HTTP request containing client headers.

    Returns:
        Response: A `FileResponse` with the script contents, or an `EmptyResponse`
        with a `NOT_MODIFIED` status if the client cache is up-to-date.

    """
    path = Path(__file__).parent / "alive-reload.js"
    timestamp = await asyncio.to_thread(os.path.getmtime, path)
    timestamp_str = f'"{timestamp}"'
    headers = {"ETag": timestamp_str, "Cache-Control": "no-cache"}
    if request.headers.get("if-none-match") == timestamp_str:
        return EmptyResponse(HTTPStatus.NOT_MODIFIED, headers)
    return FileResponse(path, headers=headers)
