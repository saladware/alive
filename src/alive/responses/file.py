"""File-based HTTP responses supporting chunked streaming and dynamic HTML injection."""

import asyncio
import mimetypes
import os
import re
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from http import HTTPStatus
from logging import getLogger
from pathlib import Path
from typing import BinaryIO

from alive.responses.base import Response

logger = getLogger(__name__)


class FileResponse(Response):
    """
    An HTTP response that streams a file back to the client.

    Handles content type detection using mimetypes and determines the payload size.
    Data is transmitted in asynchronous chunks to avoid blocking the loop.

    Attributes:
        filepath: A string or PathLike object representing the target file path.

    """

    def __init__(
        self,
        filepath: str | os.PathLike[str],
        status: HTTPStatus = HTTPStatus.OK,
        content_type: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """
        Initialize the FileResponse instance.

        Args:
            filepath: Path to the file that will be sent to the client.
            status: HTTP status code for the response. Defaults to HTTPStatus.OK.
            content_type: The content type header value. If None, it will be guessed.
            headers: Optional dictionary of additional HTTP headers.

        """
        self.filepath = filepath
        super().__init__(status, headers)
        if content_type is not None:
            self.headers["content-type"] = content_type

    async def prepare_headers(self) -> dict[str, str]:
        """
        Calculate file size and guesses the content-type before sending headers.

        Returns:
            A dictionary containing final HTTP response headers.

        """
        headers = await super().prepare_headers()
        if "content-type" not in headers:
            mimetype, _ = await asyncio.to_thread(mimetypes.guess_type, self.filepath)
            headers["content-type"] = mimetype or "application/octet-stream"
        content_length = await asyncio.to_thread(os.path.getsize, self.filepath)
        headers["content-length"] = str(content_length)

        return headers

    async def write(self, writer: asyncio.StreamWriter) -> None:
        """
        Write the HTTP headers and streams the file content in chunks.

        Args:
            writer: Stream writer for the client connection.

        """
        await self.head(writer)
        async for chunk in _read_file_chunked(self.filepath):
            writer.write(chunk)
            await writer.drain()


class HTMLInjectedHeadResponse(FileResponse):
    """
    An HTML response that dynamically inserts a custom snippet into the head tag.

    Attributes:
        pattern: A ClassVar compiled regex pattern to safely identify comments and
            the opening `<head>` tag in raw binary text.
        injection: The encoded bytes snippet intended for HTML injection.

    """

    pattern = re.compile(b"(<!--.*?-->)|(<head[^>]*?>)", re.IGNORECASE | re.DOTALL)

    def __init__(
        self,
        filepath: str | os.PathLike[str],
        injection: str,
        status: HTTPStatus = HTTPStatus.OK,
        headers: dict[str, str] | None = None,
    ) -> None:
        """
        Initialize the HTMLInjectedHeadResponse instance.

        Args:
            filepath: Path to the target HTML file.
            injection: A string snippet to inject into the document.
            status: HTTP status code for the response. Defaults to HTTPStatus.OK.
            headers: Optional dictionary of additional HTTP headers.

        """
        self.injection = injection.encode()
        super().__init__(filepath, status, "text/html", headers)

    async def prepare_headers(self) -> dict[str, str]:
        """
        Prepare headers and increases the content length by the injection size.

        Returns:
            A dictionary containing the adjusted HTTP response headers.

        """
        headers = await super().prepare_headers()
        content_length = int(self.headers["content-length"]) + len(self.injection)
        headers["content-length"] = str(content_length)
        return headers

    async def write(self, writer: asyncio.StreamWriter) -> None:
        """
        Read the HTML file, injects the snippet into the head, and sends it.

        If no `<head>` tag is detected, a warning is logged, and the snippet
        is injected at the very beginning of the response payload.

        Args:
            writer: Stream writer for the client connection.

        """
        html = await _async_read_bytes(self.filepath)

        pos = 0
        injected = False

        while True:
            match = self.pattern.search(html, pos)
            if not match:
                break

            if match.group(2):
                split_idx = match.end()
                html = html[:split_idx] + self.injection + html[split_idx:]
                injected = True
                break

            pos = match.end()

        if not injected:
            logger.warning(
                "<head> tag not found in '%s'. Injecting at the beginning.",
                self.filepath,
            )
            html = self.injection + html

        await self.head(writer)
        writer.write(html)
        await writer.drain()


@asynccontextmanager
async def _async_open_rb(path: str | os.PathLike[str]) -> AsyncGenerator[BinaryIO]:
    file_obj = await asyncio.to_thread(open, path, "rb")
    try:
        yield file_obj
    finally:
        await asyncio.to_thread(file_obj.close)


async def _read_file_chunked(
    path: str | os.PathLike[str],
    chunk_size: int = 65536,
) -> AsyncGenerator[bytes]:
    async with _async_open_rb(path) as file_obj:
        while chunk := await asyncio.to_thread(file_obj.read, chunk_size):
            yield chunk


async def _async_read_bytes(path: str | os.PathLike[str]) -> bytes:
    return await asyncio.to_thread(_read_full_file, path)


def _read_full_file(path: str | os.PathLike[str]) -> bytes:
    with Path(path).open("rb") as file_obj:
        return file_obj.read()
