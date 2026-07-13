"""HTTP response models and formatting definitions for the alive framework."""

from asyncio import StreamWriter
from http import HTTPStatus
from logging import getLogger

logger = getLogger(__name__)


class Response:
    """
    Base class representing an HTTP response.

    Provides foundational methods for preparing headers and writing the HTTP
    status line and headers to an asynchronous stream writer.

    Attributes:
        status: The HTTP status code of the response.
        headers: A dictionary containing the response HTTP headers.

    """

    def __init__(
        self,
        status: HTTPStatus = HTTPStatus.OK,
        headers: dict[str, str] | None = None,
    ) -> None:
        """
        Initialize the base HTTP response.

        Args:
            status: The HTTP status code. Defaults to `HTTPStatus.OK` (200).
            headers: Optional dictionary of HTTP headers. Defaults to None.

        """
        self.status = status
        self.headers = headers or {}

    async def prepare_headers(self) -> dict[str, str]:
        """
        Asynchronously prepares or mutates headers before sending.

        Subclasses can override this method to dynamically compute or add
        headers (e.g., dynamic content lengths or content types).

        Returns:
            dict[str, str]: The finalized dictionary of HTTP headers.

        """
        return self.headers

    async def head(self, writer: StreamWriter) -> None:
        """
        Asynchronously writes the HTTP status line and headers to the stream.

        Formats the status and header dictionaries according to HTTP/1.1
        specifications and flushes the buffer.

        Args:
            writer: The stream writer to write the head payload into.

        """
        headers = await self.prepare_headers()
        writer.write(b"HTTP/1.1 %d %s\r\n" % (self.status, self.status.phrase.encode()))
        for field, field_val in headers.items():
            fmt_args = field.encode().lower(), field_val.encode()
            writer.write(b"%s: %s\r\n" % fmt_args)
        writer.write(b"\r\n")
        await writer.drain()

    async def write(self, writer: StreamWriter) -> None:
        """
        Asynchronously writes the full HTTP response (head and body) to the stream.

        Must be implemented by subclasses to define how the body payload
        is written.

        Args:
            writer: The stream writer to receive the response.

        Raises:
            NotImplementedError: If the subclass does not implement this method.

        """
        raise NotImplementedError


class EmptyResponse(Response):
    """An HTTP response that contains headers but no body payload."""

    async def write(self, writer: StreamWriter) -> None:
        """
        Asynchronously writes only the HTTP head to the stream.

        Args:
            writer: The stream writer to receive the empty response.

        """
        return await self.head(writer)


class BytesResponse(Response):
    """
    An HTTP response that serves an in-memory binary byte array as the body.

    Automatically calculates and injects `Content-Length` and `Content-Type`
    headers based on the provided body data.

    Attributes:
        body: The raw bytes payload of the response body.

    """

    def __init__(
        self,
        body: bytes,
        status: HTTPStatus = HTTPStatus.OK,
        content_type: str = "application/octet-stream",
        headers: dict[str, str] | None = None,
    ) -> None:
        """
        Initialize the bytes response.

        Args:
            body: The binary payload for the response body.
            status: The HTTP status code. Defaults to `HTTPStatus.OK`.
            content_type: The MIME type of the content. Defaults to
                "application/octet-stream".
            headers: Optional additional HTTP headers. Defaults to None.

        """
        super().__init__(status, headers)
        self.body = body
        self.headers["content-type"] = content_type
        self.headers["content-length"] = str(len(body))

    async def write(self, writer: StreamWriter) -> None:
        """
        Asynchronously write the HTTP head followed by the binary body to the stream.

        Args:
            writer: The stream writer to receive the response bytes.

        """
        await self.head(writer)
        writer.write(self.body)
        await writer.drain()


class ErrorResponse(BytesResponse):
    """A specialized binary response for serving HTTP errors."""

    def __init__(
        self,
        status: HTTPStatus,
        message: str | None = None,
        content_type: str = "text/plain",
        headers: dict[str, str] | None = None,
    ) -> None:
        """
        Initialize the error response.

        Args:
            status: The error HTTP status code (e.g., 404, 400, 500).
            message: Optional custom string message. If omitted, defaults to the
                standard HTTP status phrase.
            content_type: The MIME type of the error message. Defaults to
                "text/plain".
            headers: Optional additional HTTP headers. Defaults to None.

        """
        if message is None:
            message = status.phrase
        super().__init__(message.encode(), status, content_type, headers)
