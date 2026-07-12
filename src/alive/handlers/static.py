import asyncio
import os
from http import HTTPStatus
from pathlib import Path

from alive.handlers import RequestHandler
from alive.request import Request
from alive.responses import (
    EmptyResponse,
    ErrorResponse,
    FileResponse,
    HTMLInjectedHeadResponse,
    Response,
)


class StaticFileHandler(RequestHandler):
    def __init__(self, root_dir: Path, html_injection: str) -> None:
        self.root_dir = root_dir
        self.html_injection = html_injection

    async def __call__(self, request: Request) -> Response:
        path = (self.root_dir / request.path.lstrip("/")).resolve()
        if not path.is_relative_to(self.root_dir):
            return ErrorResponse(HTTPStatus.BAD_REQUEST)
        if path.is_dir():
            path /= "index.html"
        if not path.is_file():
            return ErrorResponse(HTTPStatus.NOT_FOUND)
        timestamp = await asyncio.to_thread(os.path.getmtime, path)
        timestamp_str = f'"{timestamp}"'
        headers = {"ETag": timestamp_str, "Cache-Control": "no-cache"}
        if request.headers.get("if-none-match") == timestamp_str:
            return EmptyResponse(HTTPStatus.NOT_MODIFIED, headers)
        if path.suffix == ".html":
            return HTMLInjectedHeadResponse(path, self.html_injection, headers=headers)
        return FileResponse(path, headers=headers)
