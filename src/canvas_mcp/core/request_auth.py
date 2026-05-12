"""Per-request bearer-token authentication for HTTP transport.

In HTTP mode every incoming MCP request carries a Canvas API token in the
Authorization header. We extract it once at the middleware layer and stash
it in a ContextVar so any downstream code (core.client, the code-execution
sandbox, etc.) can read it without threading it through every call.

In stdio mode this module's ContextVar is never set, and consumers fall back
to the static CANVAS_API_TOKEN env var via core.config.
"""

from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp


_request_token: ContextVar[str | None] = ContextVar(
    "canvas_request_token", default=None
)


def get_request_token() -> str | None:
    """Return the bearer token for the in-flight request, or None.

    Returns None in stdio mode (no HTTP request in scope) and in HTTP requests
    that lacked a usable Authorization: Bearer header. Callers should fall
    back to config.canvas_api_token when this returns None.
    """
    return _request_token.get()


def _parse_bearer(authorization_header: str) -> str | None:
    """Extract the token from a `Bearer <token>` header value, or None.

    Tolerant of casing and surrounding whitespace; refuses empty tokens.
    """
    if not authorization_header:
        return None
    parts = authorization_header.strip().split(None, 1)
    if len(parts) != 2:
        return None
    scheme, token = parts[0], parts[1].strip()
    if scheme.lower() != "bearer" or not token:
        return None
    return token


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Pull `Authorization: Bearer <token>` into a ContextVar for the request.

    The token is set on entry and reset on exit. Requests without a usable
    bearer header pass through unchanged (handlers will see a None token and
    fall back to config or 401-equivalent behavior, depending on the consumer).
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        token = _parse_bearer(request.headers.get("authorization", ""))
        if token is None:
            return await call_next(request)
        reset_token = _request_token.set(token)
        try:
            return await call_next(request)
        finally:
            _request_token.reset(reset_token)
