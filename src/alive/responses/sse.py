"""Server-Sent Events (SSE) HTTP response implementation for real-time streaming."""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from http import HTTPStatus
from logging import getLogger
from typing import NamedTuple

from alive.responses.base import Response

logger = getLogger(__name__)


class SSEMessage(NamedTuple):
    """
    An individual Server-Sent Event message structure.

    Attributes:
        payload: A string containing the data to be transmitted.
        event: An optional string defining the specific event type.

    """

    payload: str
    event: str | None = None


class SSEResponse(Response):
    """
    An HTTP response that implements Server-Sent Events (SSE) protocol.

    Maintains a persistent connection to stream real-time updates from a shared
    listener pool and automatically sends heartbeats to prevent connection timeouts.

    Attributes:
        heartbeat_interval: An integer interval in seconds for sending heartbeats.
        queue: A unique message queue designated for this specific response instance.
        listeners: A shared set tracking active client message queues.

    """

    heartbeat_interval = 5

    def __init__(
        self,
        listeners: set[asyncio.Queue[SSEMessage]],
        status: HTTPStatus = HTTPStatus.OK,
        headers: dict[str, str] | None = None,
    ) -> None:
        """
        Initialize the SSEResponse instance and registers it to the listener pool.

        Args:
            listeners:
                A mutable set of asyncio.Queue instances where new events are
                broadcast.
            status:
                HTTP status code for the response. Defaults to HTTPStatus.OK.
            headers:
                Optional dictionary of additional HTTP headers.

        """
        self.queue: asyncio.Queue[SSEMessage] = asyncio.Queue()
        self.listeners = listeners
        self.listeners.add(self.queue)
        super().__init__(status, headers)
        self.headers["content-type"] = "text/event-stream"
        self.headers["cache-control"] = "no-cache"
        self.headers["connection"] = "keep-alive"

    async def write(self, writer: asyncio.StreamWriter) -> None:
        """
        Start the persistent event loop streaming messages to the client.

        Sends a comment heartbeat if no messages are received within the
        heartbeat_interval. Automatically handles client deregistration upon exit.

        Args:
            writer: Stream writer for the client connection.

        """
        await self.head(writer)
        async with self._listener_session():
            while not writer.is_closing():
                try:
                    message = await asyncio.wait_for(
                        self.queue.get(), timeout=self.heartbeat_interval
                    )
                except asyncio.TimeoutError:
                    writer.write(b": heartbeat\n\n")
                    await writer.drain()
                    continue

                if message.event:
                    writer.write(b"event: %s\n" % message.event.encode())
                writer.write(b"data: %s\n\n" % message.payload.encode())
                await writer.drain()

    @asynccontextmanager
    async def _listener_session(self) -> AsyncGenerator[None]:
        """Manage the lifecycle of an SSE listener registration."""
        logger.debug("SSE connection opened. total listeners: %d", len(self.listeners))
        try:
            yield
        finally:
            self.listeners.discard(self.queue)
            logger.debug(
                "SSE connection closed. total listeners: %d", len(self.listeners)
            )
