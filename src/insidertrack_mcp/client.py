"""A thin, cautious client for the InsiderTrack HTTP API.

Every tool goes through :func:`get`, which applies the upstream timeout,
turns HTTP and network failures into an ``{"error": …, "hint": …}`` object
(so the model can recover instead of seeing a stack trace), and never
raises for the caller. Writes are a separate function that only exists
when the operator enabled them.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from .config import settings

logger = logging.getLogger("insidertrack_mcp.client")

DISCLAIMER = "InsiderTrack scores public disclosures; it is a scorecard, not investment advice."


def error(message: str, hint: str | None = None) -> dict[str, Any]:
    """The shape every tool returns when something goes wrong."""
    out: dict[str, Any] = {"error": message}
    if hint:
        out["hint"] = hint
    return out


async def get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any] | list[Any]:
    """GET ``path`` from InsiderTrack; return parsed JSON or an ``error`` object."""
    clean = {k: v for k, v in (params or {}).items() if v is not None}
    url = settings.insidertrack_url.rstrip("/") + path
    try:
        async with httpx.AsyncClient(timeout=settings.upstream_timeout_seconds) as http:
            response = await http.get(url, params=clean)
    except httpx.TimeoutException:
        return error(
            "InsiderTrack did not answer in time",
            "The site may be computing scores; try again in a few seconds.",
        )
    except httpx.HTTPError as exc:
        logger.warning("upstream failure for %s: %s", path, exc)
        return error("Could not reach InsiderTrack", "Check that the site is up.")
    if response.status_code == 404:
        return error("Not found", "Use the search tool to find the right id or ticker.")
    if response.status_code >= 400:
        return error(
            f"InsiderTrack returned HTTP {response.status_code}",
            response.text[:200] or None,
        )
    if not response.headers.get("content-type", "").startswith("application/json"):
        # FastAPI's SPA fallback answers unknown paths with the web page, 200 OK.
        return error(
            "InsiderTrack answered with a web page instead of data",
            f"The path {path} is probably wrong (API paths end with a slash).",
        )
    try:
        return response.json()
    except ValueError:
        return error("InsiderTrack returned something that is not JSON")


async def post(path: str, body: dict[str, Any]) -> dict[str, Any]:
    """POST to InsiderTrack as the owner's watchlist identity. Only ``watchlist_add`` uses this."""
    if not settings.writes_enabled:
        return error("Writes are disabled on this server", "See MCP_ALLOW_WRITES in .env.example.")
    url = settings.insidertrack_url.rstrip("/") + path
    headers = {"Authorization": f"Bearer {settings.insidertrack_watchlist_token}"}
    try:
        async with httpx.AsyncClient(timeout=settings.upstream_timeout_seconds) as http:
            response = await http.post(url, json=body, headers=headers)
    except httpx.HTTPError as exc:
        logger.warning("upstream failure for %s: %s", path, exc)
        return error("Could not reach InsiderTrack", "Check that the site is up.")
    if response.status_code == 401:
        return error(
            "watchlist token rejected",
            "The token was replaced (Recover on the site) — update INSIDERTRACK_WATCHLIST_TOKEN.",
        )
    if response.status_code >= 400:
        return error(f"InsiderTrack returned HTTP {response.status_code}", response.text[:200])
    try:
        return response.json()
    except ValueError:
        return {"status": "ok"}


def is_error(payload: Any) -> bool:
    """True when :func:`get`/:func:`post` returned an error object."""
    return isinstance(payload, dict) and "error" in payload
