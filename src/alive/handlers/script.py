import asyncio
import os
from http import HTTPStatus
from pathlib import Path

from alive.request import Request
from alive.responses import EmptyResponse, FileResponse, Response


async def handle_reload_script(request: Request) -> Response:
    path = Path(__file__).parent / "alive-reload.js"
    timestamp = await asyncio.to_thread(os.path.getmtime, path)
    timestamp_str = f'"{timestamp}"'
    headers = {"ETag": timestamp_str, "Cache-Control": "no-cache"}
    if request.headers.get("if-none-match") == timestamp_str:
        return EmptyResponse(HTTPStatus.NOT_MODIFIED, headers)
    return FileResponse(path, headers=headers)
