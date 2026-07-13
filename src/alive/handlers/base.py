"""HTTP request handler protocols for the alive application."""

from typing import Protocol

from alive.request import Request
from alive.responses import Response


class RequestHandler(Protocol):
    """
    Protocol defining the structural type for HTTP request handlers.

    Any asynchronous callable implementing this protocol must accept an HTTP
    request object as a positional-only argument and return an HTTP response.
    """

    async def __call__(self, request: Request, /) -> Response:
        """
        Asynchronously process an incoming HTTP request.

        Args:
            request: The incoming HTTP request instance to handle.

        Returns:
            Response: The HTTP response generated after processing the request.

        """
        ...
