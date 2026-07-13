"""Request parsing unittests."""

import asyncio

import pytest

from alive.request import HTTPMethod, Request


def create_mock_reader(data: bytes) -> asyncio.StreamReader:
    """Create a StreamReader populated with raw data."""
    reader = asyncio.StreamReader()
    reader.feed_data(data)
    reader.feed_eof()
    return reader


async def test_parse_simple_get_request() -> None:
    """Verify parsing of a standard GET request without query parameters or body."""
    raw_request = b"GET /index.html HTTP/1.1\r\nHost: localhost\r\n\r\n"
    reader = create_mock_reader(raw_request)

    request = await Request.parse(reader)

    assert request.method == HTTPMethod.GET
    assert request.path == "/index.html"
    assert request.query == {}
    assert request.headers == {"host": "localhost"}
    assert request.body == b""


async def test_parse_request_with_query_params() -> None:
    """Verify parsing and grouping of single and multi-value query string parameters."""
    raw_request = (
        b"GET /search?q=python&tags=async&tags=web HTTP/1.1\r\nHost: web\r\n\r\n"
    )
    reader = create_mock_reader(raw_request)

    request = await Request.parse(reader)

    assert request.path == "/search"
    assert request.query == {"q": ["python"], "tags": ["async", "web"]}


async def test_parse_post_request_with_body() -> None:
    """Verify parsing of a POST request with Content-Length header and raw payload."""
    body_content = b'{"name": "test"}'
    raw_request = (
        b"POST /api/v1/data HTTP/1.1\r\n"
        b"Host: example.com\r\n"
        b"Content-Type: application/json\r\n"
        b"Content-Length: " + str(len(body_content)).encode() + b"\r\n"
        b"\r\n" + body_content
    )
    reader = create_mock_reader(raw_request)

    request = await Request.parse(reader)

    assert request.method == HTTPMethod.POST
    assert request.path == "/api/v1/data"
    assert request.headers["content-type"] == "application/json"
    assert request.body == body_content


async def test_parse_headers_case_insensitivity() -> None:
    """Verify that incoming HTTP header keys are converted to lower case."""
    raw_request = (
        b"GET / HTTP/1.1\r\nUSER-AGENT: Mozilla\r\nX-Custom-Header: Value\r\n\r\n"
    )
    reader = create_mock_reader(raw_request)

    request = await Request.parse(reader)

    assert "user-agent" in request.headers
    assert "x-custom-header" in request.headers
    assert request.headers["user-agent"] == "Mozilla"
    assert request.headers["x-custom-header"] == "Value"


async def test_parse_empty_stream_raises_connection_error() -> None:
    """Verify that an immediate EOF from the client triggers a ConnectionError."""
    reader = create_mock_reader(b"")

    with pytest.raises(ConnectionError):
        await Request.parse(reader)


@pytest.mark.parametrize(
    "malformed_data",
    [
        b"INVALID_METHOD / HTTP/1.1\r\n\r\n",  # Unsupported HTTP method
        b"GET / HTTP/1.1\r\nMissingColonHeader\r\n\r\n",  # Header without colon sep
        b"GET \r\n\r\n",  # Incomplete request line missing protocol version or path
    ],
)
async def test_parse_malformed_request_raises_value_error(
    malformed_data: bytes,
) -> None:
    """Verify that malformed or invalid HTTP requests trigger a ValueError."""
    reader = create_mock_reader(malformed_data)

    with pytest.raises(ValueError):  # noqa: PT011
        await Request.parse(reader)
