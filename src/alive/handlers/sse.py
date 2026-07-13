"""HTTP request handler for establishing and managing live-reload SSE connections."""

from asyncio import Queue

from alive.handlers import RequestHandler
from alive.request import Request
from alive.responses import Response, SSEMessage, SSEResponse


class SSERequestHandler(RequestHandler):
    """
    An HTTP request handler that establishes Server-Sent Events (SSE) connections.

    This handler manages client connections by creating an event stream response and
    registering the clients to receive broadcast messages from the shared
    listeners pool.

    Attributes:
        listeners: A reference to the set of message queues used to broadcast
            live-reload updates to all active client streams.

    """

    def __init__(self, listeners: set[Queue[SSEMessage]]) -> None:
        """
        Initialize the SSE request handler.

        Args:
            listeners: A shared set of asyncio Queues for broadcasting
                live-reload messages to connected clients.

        """
        self.listeners = listeners
        super().__init__()

    async def __call__(self, _request: Request) -> Response:
        """
        Asynchronously handles the SSE connection request.

        Args:
            _request: The incoming HTTP request (unused as SSE connections
                only require initialization).

        Returns:
            Response: An `SSEResponse` instance configured with the shared
            listeners queue.

        """
        return SSEResponse(self.listeners)
