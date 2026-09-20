"""The one write tool: registered only when enabled, acts as the owner's watchlist."""

import httpx
import pytest

from insidertrack_mcp import tools
from insidertrack_mcp.config import settings


@pytest.fixture
def writes_on(monkeypatch):
    monkeypatch.setattr(settings, "mcp_allow_writes", True)
    monkeypatch.setattr(settings, "insidertrack_watchlist_email", "owner@example.com")
    monkeypatch.setattr(settings, "insidertrack_watchlist_token", "wl-secret")


def test_writes_disabled_by_default():
    assert settings.writes_enabled is False


def test_flag_alone_does_not_enable_writes(monkeypatch):
    monkeypatch.setattr(settings, "mcp_allow_writes", True)
    assert settings.writes_enabled is False


async def test_watchlist_add_refused_when_disabled(upstream):
    result = await tools.watchlist_add("NVDA")
    assert result["error"] == "Writes are disabled on this server"
    assert not upstream.calls


async def test_watchlist_add_posts_as_the_owner(upstream, writes_on):
    route = upstream.post("/watchlist/").mock(
        return_value=httpx.Response(200, json={"id": 7, "ticker": "NVDA", "status": "added"})
    )
    result = await tools.watchlist_add("nvda")
    assert result["status"] == "added" and result["ticker"] == "NVDA"
    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer wl-secret"
    assert (
        b'"email":"owner@example.com"' in request.content
        or b'"email": "owner@example.com"' in request.content
    )


async def test_watchlist_add_reports_replaced_token(upstream, writes_on):
    upstream.post("/watchlist/").mock(
        return_value=httpx.Response(401, json={"detail": "bad token"})
    )
    result = await tools.watchlist_add("NVDA")
    assert result["error"] == "watchlist token rejected"
    assert "INSIDERTRACK_WATCHLIST_TOKEN" in result["hint"]


async def test_write_tool_not_listed_by_default():
    from insidertrack_mcp import server

    names = {t.name for t in await server.mcp.list_tools()}
    assert "watchlist_add" not in names
