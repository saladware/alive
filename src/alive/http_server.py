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
    return ErrorResponse(HTTPStatus.NOT_FOUND)


class HTTPServer:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 8000,
    ) -> None:
        self.host = host
        self.port = port
        self.request_handlers: dict[str, RequestHandler] = {}
        self.fallback_handler: RequestHandler = not_found_handler

    async def serve(self) -> None:
        server = await asyncio.start_server(
            self._handle_client_and_close, self.host, self.port
        )
        fmt_host = f"[{self.host}]" if ":" in self.host else self.host
        port = server.sockets[0].getsockname()[1]
        logger.info("listening http://%s:%d", fmt_host, port)
        async with server:
            await server.serve_forever()

    def run(self) -> None:
        try:
            asyncio.run(self.serve())
        except KeyboardInterrupt:
            sys.exit(0)

    async def _handle_client_and_close(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
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
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        async for request in _iter_conn_requests(reader):
            if request is None:
                headers = {"connection": "close"}
                response = ErrorResponse(HTTPStatus.BAD_REQUEST, headers=headers)
                await response.write(writer)
                return
            await self._handle_request(request, writer)

    async def _handle_request(
        self, request: Request, writer: asyncio.StreamWriter
    ) -> None:
        if request.method in {HTTPMethod.GET, HTTPMethod.HEAD}:
            request_handler = self.request_handlers.get(
                request.path, self.fallback_handler
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
