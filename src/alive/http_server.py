"""Asynchronous HTTP server  managing client connections and request routing."""

from __future__ import annotations

import asyncio
import logging
import sys
from http import HTTPStatus
from typing import TYPE_CHECKING

from alive.request import HTTPMethod, Request
from alive.responses import ErrorResponse, Response

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from alive.handlers import RequestHandler

logger = logging.getLogger(__name__)


KEEP_ALIVE_TIMEOUT = 30


async def not_found_handler(_request: Request) -> Response:
    """
    Fallback handler for non-existent paths.

    Args:
        _request: The incoming HTTP request instance (unused).

    Returns:
        An ErrorResponse object with HTTP status 404 (Not Found).

    """
    return ErrorResponse(HTTPStatus.NOT_FOUND)


class HTTPServer:
    """
    An asynchronous HTTP server that handles connections and routes requests.

    Attributes:
        host: A string representing the server host address.
        port: An integer representing the server port number.
        request_handlers: A dictionary mapping URL paths to their respective
            RequestHandler callables.
        fallback_handler: A RequestHandler callable invoked when no matching
            path is found in request_handlers.

    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8000,
    ) -> None:
        """
        Initialize the HTTPServer instance.

        Args:
            host: The host address to bind the server to. Defaults to "localhost".
            port: The port number to bind the server to. Defaults to 8000.

        """
        self.host = host
        self.port = port
        self.request_handlers: dict[str, RequestHandler] = {}
        self.fallback_handler: RequestHandler = not_found_handler

    async def serve(self) -> None:
        """
        Start the asynchronous TCP server and listens for incoming connections.

        Runs indefinitely until the underlying server is closed or cancelled.
        """
        server = await asyncio.start_server(
            self._handle_client_and_close,
            self.host,
            self.port,
        )
        fmt_host = f"[{self.host}]" if ":" in self.host else self.host
        port = server.sockets[0].getsockname()[1]
        logger.info("listening http://%s:%d", fmt_host, port)
        async with server:
            await server.serve_forever()

    def run(self) -> None:
        """
        Entry point to start the server event loop from synchronous context.

        Handles KeyboardInterrupt to allow graceful shutdown without backtraces.
        """
        try:
            asyncio.run(self.serve())
        except KeyboardInterrupt:
            sys.exit(0)

    async def _handle_client_and_close(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        try:
            await self._handle_client(reader, writer)
        except ConnectionError:
            logger.debug("Client disconnected")
        except Exception:
            logger.exception("internal server error")
        finally:
            await _cleanup_conn(writer)

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        async for request in _iter_conn_requests(reader):
            if request is None:
                headers = {"connection": "close"}
                response = ErrorResponse(HTTPStatus.BAD_REQUEST, headers=headers)
                await response.write(writer)
                return
            await self._handle_request(request, writer)

    async def _handle_request(
        self,
        request: Request,
        writer: asyncio.StreamWriter,
    ) -> None:
        if request.method in {HTTPMethod.GET, HTTPMethod.HEAD}:
            request_handler = self.request_handlers.get(
                request.path,
                self.fallback_handler,
            )
            response = await request_handler(request)
        else:
            response = ErrorResponse(HTTPStatus.METHOD_NOT_ALLOWED)
        response.headers.setdefault(
            "connection",
            "close" if request.headers.get("connection") == "close" else "keep-alive",
        )
        logger.info("", extra={"status": response.status, "request": request})
        if request.method is HTTPMethod.HEAD:
            await response.head(writer)
        else:
            await response.write(writer)


async def _iter_conn_requests(
    reader: asyncio.StreamReader,
) -> AsyncGenerator[Request | None]:
    try:
        request = await asyncio.wait_for(Request.parse(reader), KEEP_ALIVE_TIMEOUT)
    except ConnectionError as exc:
        logger.debug("Client disconnected during request read: %s", exc)
        return
    except TimeoutError:
        logger.debug("Keep alive timeout. disconnect")
        return
    except ValueError:
        logger.exception("Bad request syntax")
        yield None
    else:
        logger.debug("New incoming request: %s", request)
        yield request


async def _cleanup_conn(writer: asyncio.StreamWriter) -> None:
    writer.close()
    try:
        await writer.wait_closed()
    except ConnectionError:
        logger.debug("Connection closed abruptly by client during cleanup")
