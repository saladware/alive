"""
HTTP request parsing utilities.

This module provides data structures and async functions to parse incoming
HTTP requests from an asynchronous stream.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, NamedTuple
from urllib.parse import parse_qs, urlparse

if TYPE_CHECKING:
    from asyncio import StreamReader


class HTTPMethod(str, Enum):
    """HTTP Methods."""

    GET = "GET"
    HEAD = "HEAD"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    OPTIONS = "OPTIONS"
    PATCH = "PATCH"
    TRACE = "TRACE"
    CONNECT = "CONNECT"


class Request(NamedTuple):
    """
    Represents a parsed HTTP request.

    Attributes:
        method: The HTTP method used (e.g., GET, POST).
        path: The target URL path component.
        query: Query string parameters mapped to lists of values.
        headers: Lowercase header names mapped to their values.
        body: The raw byte content of the request body.

    """

    method: HTTPMethod
    path: str
    query: dict[str, list[str]]
    headers: dict[str, str]
    body: bytes

    @classmethod
    async def parse(cls, reader: StreamReader) -> Request:
        """
        Parse an incoming HTTP request from a stream reader.

        Args:
            reader: The async stream reader to read the request from.

        Returns:
            A new Request instance populated with parsed data.

        Raises:
            ConnectionError: If the client disconnects before sending data.
            ValueError: If the request is malformed.

        """
        request_line = await reader.readline()
        if not request_line:
            raise _disconnected
        method, full_path, _ = request_line.decode().split(maxsplit=2)
        parsed_url = urlparse(full_path)
        headers = await _parse_headers(reader)
        return cls(
            method=HTTPMethod(method),
            path=parsed_url.path,
            query=parse_qs(parsed_url.query),
            headers=headers,
            body=await _parse_body(reader, headers),
        )


_disconnected = ConnectionError("Client disconnected")


async def _parse_headers(reader: StreamReader) -> dict[str, str]:
    headers: dict[str, str] = {}
    while line := (await reader.readline()).strip().decode():
        header_name, header_val = line.split(":", maxsplit=1)
        headers[header_name.lower().strip()] = header_val.strip()
    return headers


async def _parse_body(reader: StreamReader, headers: dict[str, str]) -> bytes:
    content_length = headers.get("content-length")
    if content_length:
        return await reader.read(int(content_length))
    return b""
