"""Command-line interface entry point for launching the live-reload HTTP server."""

from __future__ import annotations

import json
from argparse import ArgumentParser
from logging import DEBUG, getLogger
from logging.config import dictConfig
from pathlib import Path

from alive.live_server import LiveServer

DEFAULT_PORT = 8000

logger = getLogger(__name__)


def app() -> None:
    """
    Parse command-line arguments and starts the live HTTP server.

    This function initializes the logging configuration from a local JSON file,
    sets up the CLI argument parser, handles optional debug logging activation,
    and runs the `LiveServer` blockingly.
    """
    logging_file = Path(__file__).parent / "logging_config.json"
    with logging_file.open("r", encoding="utf-8") as file_obj:
        dictConfig(json.load(file_obj))

    parser = ArgumentParser("alive", description="Live HTTP Server")

    parser.add_argument("-p", "--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("root_dir")
    parser.add_argument("--debug", action="store_true")

    args = parser.parse_args()
    if args.debug:
        getLogger("alive").setLevel(DEBUG)
    server = LiveServer(args.root_dir, args.host, args.port)
    server.run()


if __name__ == "__main__":
    app()
