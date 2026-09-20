"""The search tool: shape, caps and error handling."""

import httpx
from conftest import fixture

from insidertrack_mcp import server


async def test_search_returns_politicians_with_ids(upstream):
    upstream.get("/search/").mock(return_value=httpx.Response(200, json=fixture("search_pelosi")))
    result = await server.search("pelosi")
    assert result["politicians"] == [
        {
            "id": 12,
            "name": "Nancy Pelosi",
            "chamber": "house",
            "party": "D",
            "state": "CA",
            "tracked": True,
        }
    ]
    assert result["tickers"] == []
    assert "disclaimer" in result and "as_of" in result
    assert upstream.calls.last.request.url.params["q"] == "pelosi"


async def test_search_rejects_empty_query(upstream):
    result = await server.search("   ")
    assert result["error"].startswith("query must be")
    assert not upstream.calls


async def test_search_upstream_down_is_an_error_object(upstream):
    upstream.get("/search/").mock(side_effect=httpx.ConnectError("refused"))
    result = await server.search("nvda")
    assert result == {"error": "Could not reach InsiderTrack", "hint": "Check that the site is up."}


async def test_search_http_500_is_an_error_object(upstream):
    upstream.get("/search/").mock(return_value=httpx.Response(500, text="boom"))
    result = await server.search("nvda")
    assert result["error"] == "InsiderTrack returned HTTP 500"
    assert result["hint"] == "boom"


async def test_tool_is_registered_with_a_description():
    tools = await server.mcp.list_tools()
    names = {t.name for t in tools}
    assert "search" in names
    search = next(t for t in tools if t.name == "search")
    assert "politician id" in search.description
    assert search.input_schema["required"] == ["query"]
