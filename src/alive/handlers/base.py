from typing import Protocol

from alive.request import Request
from alive.responses import Response


class RequestHandler(Protocol):
    async def __call__(self, request: Request, /) -> Response: ...
