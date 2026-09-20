"""Every tool against a recorded InsiderTrack response: shape, caps, validation."""

import httpx
from conftest import fixture

from insidertrack_mcp import tools


def ok(upstream, path, name, **kw):
    return upstream.get(path, **kw).mock(return_value=httpx.Response(200, json=fixture(name)))


# ── congress_trades ───────────────────────────────────────────────────────────


async def test_congress_trades_passes_filters_and_flattens_rows(upstream):
    route = ok(upstream, "/trades/", "trades_nvda")
    result = await tools.congress_trades(
        ticker="nvda", direction="buy", since="2026-01-01", limit=2
    )
    params = route.calls.last.request.url.params
    assert params["ticker"] == "NVDA" and params["direction"] == "buy"
    assert params["since"] == "2026-01-01" and params["limit"] == "2"
    assert "until" not in params
    assert result["total_matching"] == 211
    first = result["trades"][0]
    assert first["member"] == {
        "id": 57,
        "name": "John McGuire",
        "chamber": "house",
        "party": "R",
        "state": "VA",
    }
    assert first["amount"] == "$1,001 - $15,000" and first["direction"] == "buy"
    assert first["filing_url"].startswith("https://")
    assert "raw_data" not in first and "id" not in first


async def test_congress_trades_rejects_bad_ticker_and_date(upstream):
    assert (await tools.congress_trades(ticker="not a ticker"))["error"].startswith("ticker")
    assert "since must be a date" in (await tools.congress_trades(since="yesterday"))["error"]
    assert not upstream.calls


async def test_congress_trades_caps_limit(upstream):
    route = ok(upstream, "/trades/", "trades_nvda")
    await tools.congress_trades(limit=5000)
    assert route.calls.last.request.url.params["limit"] == "100"


# ── ticker_signal / top_signals ───────────────────────────────────────────────


async def test_ticker_signal_finds_one_ticker_with_reasons(upstream):
    ok(upstream, "/signals/", "signals")
    result = await tools.ticker_signal("kmx")
    assert result["ticker"] == "KMX" and result["score"] == 74
    assert result["label"] == "Strong Watch" and result["signal"] == "NEUTRAL"
    assert result["sub_scores"]["insider"] == 30
    assert result["congress"]["buy_dollars"] == "$7K"
    assert any("Cluster buy" in r for r in result["reasons"])
    assert result["as_of"].startswith("2026-09-20")


async def test_ticker_signal_unknown_ticker_explains_why(upstream):
    ok(upstream, "/signals/", "signals")
    result = await tools.ticker_signal("ZZZZ")
    assert result["error"] == "ZZZZ has no score right now"
    assert "tracked member of Congress" in result["hint"]


async def test_top_signals_sorted_and_filtered(upstream):
    ok(upstream, "/signals/", "signals")
    result = await tools.top_signals(limit=5)
    assert [s["ticker"] for s in result["signals"]] == ["KMX", "NVDA"]
    assert "reasons" not in result["signals"][0]
    assert result["scored_tickers"] == 2
    only_high = await tools.top_signals(min_score=70)
    assert [s["ticker"] for s in only_high["signals"]] == ["KMX"]


# ── cluster_buys ──────────────────────────────────────────────────────────────


async def test_cluster_buys_formats_dollars_and_clamps(upstream):
    route = ok(upstream, "/insiders/clusters", "clusters")
    result = await tools.cluster_buys(days=9999, min_buyers=0, limit=2)
    params = route.calls.last.request.url.params
    assert params["days"] == "365" and params["min_buyers"] == "1"
    assert len(result["clusters"]) == 2
    assert all(c["ticker"] != "NONE" for c in result["clusters"])  # unlisted filers dropped
    assert result["clusters"][0] == {
        "ticker": "BABA",
        "company": "Alibaba Group Holding Ltd",
        "buyers": 2,
        "buys": 3,
        "dollars": "$25.7M",
        "last_buy": "2026-08-25",
    }


# ── member_track_record ───────────────────────────────────────────────────────


async def test_member_track_record_merges_record_and_member(upstream):
    ok(upstream, "/politicians/1/track-record", "track_record_1")
    ok(upstream, "/politicians/1", "politician_1")
    result = await tools.member_track_record(1, recent_trades=1)
    assert result["member"]["name"] == "Nancy Pelosi"
    assert result["weight_in_score"] == 1.2
    assert result["buys"]["measured"] == 21
    assert result["buys"]["windows"]["30d"] == {
        "n": 21,
        "win_rate_pct": 81.0,
        "avg_return_pct": 5.97,
        "avg_excess_vs_spy_pct": 4.06,
        "beat_spy_rate_pct": 71.4,
    }
    assert len(result["buys"]["recent"]) == 1
    assert result["buys"]["recent"][0]["ticker"] == "INTC"
    assert result["buys"]["recent"][0]["return_pct"]["30d"] == 20.57
    assert result["sales"]["windows"]["90d"]["n"] == 4


async def test_member_track_record_unknown_id(upstream):
    upstream.get("/politicians/999/track-record").mock(return_value=httpx.Response(404))
    result = await tools.member_track_record(999)
    assert result["error"] == "Not found"


# ── leaderboard ───────────────────────────────────────────────────────────────


async def test_leaderboard_rows(upstream):
    ok(upstream, "/politicians/leaderboard", "leaderboard")
    result = await tools.leaderboard(limit=1)
    assert result["as_of"] == "2026-09-20"
    assert result["ranked"] == [
        {
            "rank": 1,
            "member": {
                "id": 31,
                "name": "Ed Case",
                "chamber": "house",
                "party": "D",
                "state": "HI",
            },
            "buys_measured": 10,
            "beat_spy_rate_pct": 90.0,
            "weight_in_score": 1.4,
        }
    ]


# ── signal_outcomes ───────────────────────────────────────────────────────────


async def test_signal_outcomes_reshapes_windows(upstream):
    route = ok(upstream, "/outcomes/stats", "outcomes_stats")
    result = await tools.signal_outcomes(score_version=4)
    assert route.calls.last.request.url.params["score_version"] == "4"
    assert result["score_version"] == 4 and result["total_snapshots"] == 135
    strong = result["labels"][0]
    assert strong["label"] == "Strong Watch"
    assert strong["d30"] == {"resolved": 0, "up": 0, "down": 0, "flat": 0, "win_rate_pct": None}
    assert result["versions"][0]["version"] == 1


# ── model_desk ────────────────────────────────────────────────────────────────


async def test_model_desk_today_and_history(upstream):
    ok(upstream, "/ai-desk/today", "desk_today")
    ok(upstream, "/ai-desk/calls", "desk_calls")
    result = await tools.model_desk(history=2)
    assert result["brief"]["date"] == "2026-09-20"
    assert result["brief"]["summary"].startswith("Today's data features")
    assert result["brief"]["model"] == "gemini/gemini-flash-latest"
    call = result["todays_calls"][0]
    assert call["ticker"] == "CPAY" and call["direction"] == "bearish"
    assert call["horizon_days"] == 90 and call["resolves_on"] == "2026-12-19"
    assert "scorecard" in result
    assert len(result["past_calls"]) == 2


async def test_model_desk_without_history_makes_one_call(upstream):
    ok(upstream, "/ai-desk/today", "desk_today")
    calls = upstream.get("/ai-desk/calls")
    result = await tools.model_desk()
    assert "past_calls" not in result
    assert not calls.called


async def test_every_tool_has_disclaimer_and_as_of(upstream):
    ok(upstream, "/signals/", "signals")
    for result in (await tools.top_signals(), await tools.ticker_signal("KMX")):
        assert result["disclaimer"].endswith("not investment advice.")
        assert result["as_of"]
