from asyncio import StreamWriter
from http import HTTPStatus
from logging import getLogger

logger = getLogger(__name__)


class Response:
    def __init__(
        self,
        status: HTTPStatus = HTTPStatus.OK,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status = status
        self.headers = headers or {}

    async def prepare_headers(self) -> dict[str, str]:
        return self.headers

    async def head(self, writer: StreamWriter) -> None:
        headers = await self.prepare_headers()
        writer.write(b"HTTP/1.1 %d %s\r\n" % (self.status, self.status.phrase.encode()))
        for field, field_val in headers.items():
            fmt_args = field.encode().lower(), field_val.encode()
            writer.write(b"%s: %s\r\n" % fmt_args)
        writer.write(b"\r\n")
        await writer.drain()

    async def write(self, writer: StreamWriter) -> None:
        raise NotImplementedError


class EmptyResponse(Response):
    async def write(self, writer: StreamWriter) -> None:
        return await self.head(writer)


class BytesResponse(Response):
    def __init__(
        self,
        body: bytes,
        status: HTTPStatus = HTTPStatus.OK,
        content_type: str = "application/octet-stream",
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(status, headers)
        self.body = body
        self.headers["content-type"] = content_type
        self.headers["content-length"] = str(len(body))

    async def write(self, writer: StreamWriter) -> None:
        await self.head(writer)
        writer.write(self.body)
        await writer.drain()


class ErrorResponse(BytesResponse):
    def __init__(
        self,
        status: HTTPStatus,
        message: str | None = None,
        content_type: str = "text/plain",
        headers: dict[str, str] | None = None,
    ) -> None:
        if message is None:
            message = status.phrase
        super().__init__(message.encode(), status, content_type, headers)
