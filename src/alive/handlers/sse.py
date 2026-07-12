from asyncio import Queue

from alive.handlers import RequestHandler
from alive.request import Request
from alive.responses import Response, SSEMessage, SSEResponse


class SSERequestHandler(RequestHandler):
    def __init__(self, listeners: set[Queue[SSEMessage]]) -> None:
        self.listeners = listeners
        super().__init__()

    async def __call__(self, _request: Request) -> Response:
        return SSEResponse(self.listeners)
