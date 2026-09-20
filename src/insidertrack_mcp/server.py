"""The MCP server: tools, resources and prompts over the InsiderTrack API.

Run it two ways:

* ``insidertrack-mcp`` (stdio) — a local client such as Claude Code starts it
  as a subprocess; no network, no tokens.
* ``MCP_TRANSPORT=streamable-http insidertrack-mcp`` — serves ``/mcp`` over
  HTTP for Claude Desktop, claude.ai and other remote clients; every request
  must carry one of the bearer tokens in ``MCP_TOKENS``.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from . import tools
from .config import settings
from .version import __version__

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
audit = logging.getLogger("insidertrack_mcp.audit")

INSTRUCTIONS = """\
InsiderTrack tracks the stock trades of U.S. Congress members, corporate insiders
(SEC Form 4) and institutional investors from their public disclosures, scores each
ticker 0-100 on who is buying, weights each member by how their past buys performed
against SPY, and records whether every score went up or down 30/60/90 days later.

Use `search` first when you have a name or ticker fragment and need an id. Results
are capped; narrow the filters rather than asking for more. Everything here is a
scorecard of public filings, not investment advice — say so when it matters.
"""

mcp = MCPServer(
    name="InsiderTrack",
    version=__version__,
    instructions=INSTRUCTIONS,
    website_url="https://github.com/mrgutierrezmario/insidertrack",
)


ToolFn = Callable[..., Awaitable[dict[str, Any]]]


def audited(fn: ToolFn) -> ToolFn:
    """Log one line per tool call: tool, arguments, rows returned, duration."""

    @wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
        started = time.perf_counter()
        result = await fn(*args, **kwargs)
        rows = sum(len(v) for v in result.values() if isinstance(v, list))
        audit.info(
            "tool=%s args=%s rows=%d error=%s ms=%d",
            fn.__name__,
            kwargs or args,
            rows,
            result.get("error", "-"),
            (time.perf_counter() - started) * 1000,
        )
        return result

    return wrapper


# ── Tools ─────────────────────────────────────────────────────────────────────
# Every tool is read-only and idempotent; the annotations tell clients so.

for _fn in tools.TOOLS:
    mcp.add_tool(
        audited(_fn),
        name=_fn.__name__,
        annotations=ToolAnnotations(
            read_only_hint=True, idempotent_hint=True, open_world_hint=False
        ),
    )

# The one write exists only when the operator enabled it and gave the server
# an identity to write as; otherwise clients never even see it.
if settings.writes_enabled:
    for _fn in tools.WRITE_TOOLS:
        mcp.add_tool(
            audited(_fn),
            name=_fn.__name__,
            annotations=ToolAnnotations(
                read_only_hint=False, destructive_hint=False, idempotent_hint=True
            ),
        )


# ── HTTP: bearer auth, rate limit, health ─────────────────────────────────────


class BearerAuth(BaseHTTPMiddleware):
    """Require one of the configured tokens on every request except ``/health``."""

    def __init__(self, app: Any) -> None:
        """Wrap ``app``; per-client call timestamps live for the process lifetime."""
        super().__init__(app)
        self.calls: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(
        self, request: Request, call_next: Callable[..., Awaitable[Response]]
    ) -> Response:
        """Reject a missing or unknown token (401) or a client over the limit (429)."""
        if request.url.path == "/mcp/health":
            return await call_next(request)
        header = request.headers.get("authorization", "")
        token = header.removeprefix("Bearer ").strip() if header.startswith("Bearer ") else ""
        name = settings.tokens.get(token)
        if not name:
            return JSONResponse(
                {"error": "unauthorized"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
        now = time.monotonic()
        window = self.calls[name]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= settings.rate_limit_per_minute:
            return JSONResponse({"error": "rate limited"}, status_code=429)
        window.append(now)
        request.state.client_name = name
        return await call_next(request)


def http_app() -> Any:
    """The Starlette app for the HTTP transport, with auth and a health route."""
    # Mounted under /mcp: the Funnel forwards the path as-is, so the MCP
    # endpoint is /mcp and the open health route sits beside it at /mcp/health.
    app = mcp.streamable_http_app(host=settings.mcp_host, streamable_http_path="/mcp")

    async def health(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "version": __version__})

    app.add_route("/mcp/health", health, methods=["GET"])
    app.add_middleware(BearerAuth)
    return app


def main() -> None:
    """Entry point: pick the transport from ``MCP_TRANSPORT``."""
    if settings.mcp_transport == "streamable-http":
        if not settings.tokens:
            raise SystemExit("MCP_TOKENS must be set to serve over HTTP")
        import uvicorn

        uvicorn.run(http_app(), host=settings.mcp_host, port=settings.mcp_port, log_level="info")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
