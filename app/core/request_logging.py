"""One safe JSON access record per request, with no bodies, query strings or credentials."""

import json
import logging
import re
from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("takeaway.requests")
_REQUEST_ID = re.compile(r"[A-Za-z0-9_-]{1,64}", re.ASCII)


def configure_request_logging() -> None:
    # Do not inherit Uvicorn's text prefix or configure unrelated application loggers.
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


class RequestLoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = perf_counter()
        supplied = [value for name, value in scope["headers"] if name.lower() == b"x-request-id"]
        candidate = supplied[0].decode("latin-1") if len(supplied) == 1 else ""
        request_id = candidate if _REQUEST_ID.fullmatch(candidate) else uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        status_code = 500

        async def send_with_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = [
                    (k, v) for k, v in message.get("headers", []) if k.lower() != b"x-request-id"
                ]
                message = {**message, "headers": headers + [(b"x-request-id", request_id.encode())]}
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            route = scope.get("route")
            logger.info(
                json.dumps(
                    {
                        "timestamp": datetime.now(UTC)
                        .isoformat(timespec="microseconds")
                        .replace("+00:00", "Z"),
                        "event": "request",
                        "request_id": request_id,
                        "method": scope["method"],
                        # Never log raw paths: unknown paths can themselves contain secrets.
                        "route": getattr(route, "path", "unmatched"),
                        "status": status_code,
                        "duration_ms": round((perf_counter() - started) * 1000, 3),
                    },
                    separators=(",", ":"),
                )
            )


class SafeServerFormatter(logging.Formatter):
    """Keep Uvicorn lifecycle logs JSON and suppress exception/SQL parameter dumps."""

    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "event": "server",
                "level": record.levelname.lower(),
                "process": record.process,
                "message": "Unhandled application error"
                if record.exc_info
                else record.getMessage(),
            },
            separators=(",", ":"),
        )
