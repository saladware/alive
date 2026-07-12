from __future__ import annotations

import logging
from http import HTTPStatus
from typing import ClassVar

from alive.request import Request

GREY = "\033[90m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
BOLD_RED = "\033[1;31m"
BLUE = "\033[34m"
CYAN = "\033[36m"
RESET = "\033[0m"


class ColorFormatter(logging.Formatter):
    colors: ClassVar = {
        logging.DEBUG: CYAN,
        logging.INFO: GREEN,
        logging.WARNING: YELLOW,
        logging.ERROR: RED,
        logging.CRITICAL: BOLD_RED,
    }

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:  # noqa: N802
        formatted_time = super().formatTime(record, datefmt)
        return f"{GREY}{formatted_time}{RESET}"

    def format(self, record: logging.LogRecord) -> str:
        log_color = self.colors.get(record.levelno, RESET)
        orig_levelname = record.levelname
        aligned_levelname = f"{orig_levelname:<8}"
        record.levelname = f"{log_color}{aligned_levelname}{RESET}"
        record_fmt = super().format(record)
        record.levelname = orig_levelname
        return record_fmt


class RequestColorFormatter(ColorFormatter):
    method_colors: ClassVar[dict[str, str]] = {
        "GET": GREEN,
        "POST": YELLOW,
        "PUT": CYAN,
        "PATCH": CYAN,
        "DELETE": RED,
    }
    status_colors: ClassVar[dict[int, str]] = {
        200: GREEN,
        300: YELLOW,
        400: RED,
        500: BOLD_RED,
    }

    def format(self, record: logging.LogRecord) -> str:
        req_str = self._format_request(getattr(record, "request", None))
        status_str = self._format_status(getattr(record, "status", None))

        parts = [part for part in (req_str, status_str) if part]

        orig_msg = record.msg
        if parts:
            record.msg = " — ".join(parts)

        record_fmt = super().format(record)
        record.msg = orig_msg
        return record_fmt

    def _format_request(self, req: Request | None) -> str | None:
        if not isinstance(req, Request):
            return None
        method_color = self.method_colors.get(req.method.value, RESET)
        return f"{method_color}{req.method}{RESET} {req.path}"

    def _format_status(self, status: HTTPStatus | None) -> str | None:
        if not isinstance(status, HTTPStatus):
            return None
        status_color = self.status_colors.get(status // 100 * 100, RESET)
        return f"{status_color}{status.value} {status.phrase}{RESET}"
