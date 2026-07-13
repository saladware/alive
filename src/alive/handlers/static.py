"""HTTP request handler for serving and injecting scripts into static assets."""

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
    """
    An HTTP request handler for serving static files from a root directory.

    This handler resolves requested paths against a secure root directory, serves
    index files for directories, implements browser caching using `ETag` and
    `If-None-Match`, and injects custom HTML/scripts into served HTML documents.

    Attributes:
        root_dir: The base directory path from which static files are served.
        html_injection: The HTML/JavaScript code snippet to inject into the
            `<head>` of all HTML files.

    """

    def __init__(self, root_dir: Path, html_injection: str) -> None:
        """
        Initialize the static file handler.

        Args:
            root_dir: The secure root directory for file lookups.
            html_injection: The text snippet to insert into HTML responses.

        """
        self.root_dir = root_dir
        self.html_injection = html_injection

    async def __call__(self, request: Request) -> Response:
        """
        Asynchronously processes a request to serve a static file.

        Resolves the requested path, enforces directory traversal protection,
        checks for client-side caching, and chooses the appropriate response
        type based on the file content and cache state.

        Args:
            request: The incoming HTTP request containing the targeted file path
                and client headers.

        Returns:
            Response: A specific response subclass which can be one of:
                - `ErrorResponse`: If directory traversal is attempted (400)
                  or the file does not exist (404).
                - `EmptyResponse`: If the file has not been modified (304).
                - `HTMLInjectedHeadResponse`: For `.html` files requiring code
                   injection.
                - `FileResponse`: For all other valid static files.

        """
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
