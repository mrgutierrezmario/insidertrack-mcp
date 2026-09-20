"""Resources and prompts."""

import httpx
from conftest import fixture

from insidertrack_mcp import extras, server


async def test_brief_resource_renders_text(upstream):
    upstream.get("/ai-desk/today").mock(
        return_value=httpx.Response(200, json=fixture("desk_today"))
    )
    text = await extras.brief_today()
    assert text.startswith("InsiderTrack Model Desk — 2026-09-20")
    assert "Today's data features" in text
    assert "- CPAY: bearish over 90 days" in text


async def test_brief_resource_when_no_brief_yet(upstream):
    upstream.get("/ai-desk/today").mock(
        return_value=httpx.Response(200, json={"brief": None, "calls": [], "stats": {}})
    )
    assert (await extras.brief_today()).startswith("No brief yet today")


async def test_sources_health_lists_each_source(upstream):
    upstream.get("/health").mock(return_value=httpx.Response(200, json=fixture("health")))
    text = await extras.sources_health()
    assert "errors in the last 24 h: 0" in text
    assert "- Senate EFD: ok; last success 2026-09-20T16:29:40+00:00" in text
    assert "- House Clerk PTRs: stale" in text and "error: HTTP 503" in text


async def test_resources_and_prompts_are_registered():
    uris = {str(r.uri) for r in await server.mcp.list_resources()}
    assert uris == {"insidertrack://brief/today", "insidertrack://sources/health"}
    prompts = {
        p.name: [a.name for a in (p.arguments or [])] for p in await server.mcp.list_prompts()
    }
    assert prompts == {"morning_brief": [], "due_diligence": ["ticker"]}


async def test_due_diligence_prompt_names_the_tools_in_order():
    result = await server.mcp.get_prompt("due_diligence", {"ticker": " nvda "})
    text = result.messages[0].content.text
    assert "ticker_signal('NVDA')" in text
    assert (
        text.index("ticker_signal") < text.index("congress_trades") < text.index("signal_outcomes")
    )
    assert text.endswith("not investment advice.")


async def test_morning_brief_prompt_mentions_the_health_resource():
    result = await server.mcp.get_prompt("morning_brief", {})
    assert "insidertrack://sources/health" in result.messages[0].content.text
