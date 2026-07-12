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

from alive.protocols import StrPath
from alive.responses.base import Response

logger = getLogger(__name__)


class FileResponse(Response):
    def __init__(
        self,
        filepath: StrPath,
        status: HTTPStatus = HTTPStatus.OK,
        content_type: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.filepath = filepath
        super().__init__(status, headers)
        if content_type is not None:
            self.headers["content-type"] = content_type

    async def prepare_headers(self) -> dict[str, str]:
        headers = await super().prepare_headers()
        if "content-type" not in headers:
            mimetype, _ = await asyncio.to_thread(mimetypes.guess_type, self.filepath)
            headers["content-type"] = mimetype or "application/octet-stream"
        content_length = await asyncio.to_thread(os.path.getsize, self.filepath)
        headers["content-length"] = str(content_length)

        return headers

    async def write(self, writer: asyncio.StreamWriter) -> None:
        await self.head(writer)
        async for chunk in read_file_chunked(self.filepath):
            writer.write(chunk)
            await writer.drain()


class HTMLInjectedHeadResponse(FileResponse):
    pattern = re.compile(b"(<!--.*?-->)|(<head[^>]*?>)", re.IGNORECASE | re.DOTALL)

    def __init__(
        self,
        filepath: str | os.PathLike[str],
        injection: str,
        status: HTTPStatus = HTTPStatus.OK,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.injection = injection.encode()
        super().__init__(filepath, status, "text/html", headers)

    async def prepare_headers(self) -> dict[str, str]:
        headers = await super().prepare_headers()
        content_length = int(self.headers["content-length"]) + len(self.injection)
        headers["content-length"] = str(content_length)
        return headers

    async def write(self, writer: asyncio.StreamWriter) -> None:
        html = await async_read_bytes(self.filepath)

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
async def async_open_rb(path: StrPath) -> AsyncGenerator[BinaryIO]:
    file_obj = await asyncio.to_thread(open, path, "rb")
    try:
        yield file_obj
    finally:
        await asyncio.to_thread(file_obj.close)


async def read_file_chunked(
    path: StrPath, chunk_size: int = 65536
) -> AsyncGenerator[bytes]:
    async with async_open_rb(path) as file_obj:
        while chunk := await asyncio.to_thread(file_obj.read, chunk_size):
            yield chunk


async def async_read_bytes(path: StrPath) -> bytes:
    return await asyncio.to_thread(_read_full_file, path)


def _read_full_file(path: StrPath) -> bytes:
    with Path(path).open("rb") as file_obj:
        return file_obj.read()
