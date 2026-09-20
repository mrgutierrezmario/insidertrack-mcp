"""The tools, one function each, registered on the server in ``server.py``.

Each tool validates its inputs, calls one or two InsiderTrack endpoints
through :mod:`client`, trims the response to what a model needs (capped
rows, formatted dollars, no internal ids it cannot use) and wraps it with
``as_of`` and the disclaimer. Errors are returned, never raised.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Literal

from . import client
from .formatting import cap_rows, clip_text, dollars, envelope

_TICKER = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")


def _ticker(value: str) -> str | None:
    """Normalise a ticker; ``None`` when it cannot be one."""
    value = value.strip().upper()
    return value if _TICKER.match(value) else None


def _iso(value: str | None, name: str) -> tuple[str | None, dict[str, Any] | None]:
    """Validate an optional ``YYYY-MM-DD`` argument."""
    if value is None:
        return None, None
    try:
        return date.fromisoformat(value).isoformat(), None
    except ValueError:
        return None, client.error(f"{name} must be a date like 2026-03-31")


def _politician(p: dict[str, Any] | None) -> dict[str, Any] | None:
    if not p:
        return None
    return {k: p.get(k) for k in ("id", "name", "chamber", "party", "state")}


# ── search ────────────────────────────────────────────────────────────────────


async def search(query: str) -> dict[str, Any]:
    """Find members of Congress, tickers, 13F funds and Fed officials by name or symbol.

    Use this first when you have a name or part of a ticker and need the
    politician id, fund id or exact symbol that the other tools take.
    Matching is case-insensitive and partial ("pelosi", "NVD", "berkshire").

    Args:
        query: A name or ticker fragment, 1-80 characters.
    """
    query = query.strip()
    if not 1 <= len(query) <= 80:
        return client.error("query must be 1-80 characters")
    data = await client.get("/search/", {"q": query})
    if client.is_error(data):
        return data
    # The site's search does not cover 13F funds; match their names here.
    funds = await client.get("/whales/")
    fund_hits = (
        [
            {"id": f.get("id"), "name": f.get("name")}
            for f in funds
            if query.lower() in (f.get("name") or "").lower()
        ]
        if isinstance(funds, list)
        else []
    )
    return envelope(
        {
            "funds": cap_rows(fund_hits),
            "politicians": [
                {**_politician(p), "tracked": p.get("is_tracked")}
                for p in cap_rows(data.get("politicians", []))
            ],
            "tickers": cap_rows(data.get("tickers", [])),
            "fed_officials": [
                {"id": f["id"], "name": f["name"], "title": f.get("title")}
                for f in cap_rows(data.get("fed_officials", []))
            ],
        }
    )


# ── congress_trades ───────────────────────────────────────────────────────────


async def congress_trades(
    ticker: str | None = None,
    politician_id: int | None = None,
    direction: Literal["buy", "sell"] | None = None,
    owner: Literal["self", "spouse", "child", "joint"] | None = None,
    asset_type: Literal["stock", "option", "other"] | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 25,
) -> dict[str, Any]:
    """Stock trades disclosed by members of Congress (House and Senate PTRs).

    Filter by ticker and/or politician id (from `search`), direction, who in
    the household traded, asset type, and a date range on the trade date.
    Newest first. Amounts are the dollar brackets the law requires, not exact
    figures. `direction` already treats a put purchase as the bearish bet it is.

    Args:
        ticker: Exact symbol, e.g. NVDA.
        politician_id: From `search`.
        direction: buy or sell.
        owner: self, spouse, child or joint.
        asset_type: stock, option or other.
        since: Earliest trade date, YYYY-MM-DD.
        until: Latest trade date, YYYY-MM-DD.
        limit: Rows to return, 1-100 (default 25).
    """
    params: dict[str, Any] = {"limit": max(1, min(limit, 100))}
    if ticker is not None:
        if (sym := _ticker(ticker)) is None:
            return client.error("ticker does not look like a symbol", "Try search first")
        params["ticker"] = sym
    for name, value in (("since", since), ("until", until)):
        iso, err = _iso(value, name)
        if err:
            return err
        params[name] = iso
    params.update(
        politician_id=politician_id, direction=direction, owner=owner, asset_type=asset_type
    )
    data = await client.get("/trades/", params)
    if client.is_error(data):
        return data
    items = data.get("items", [])
    return envelope(
        {
            "total_matching": data.get("total"),
            "trades": [
                {
                    "member": _politician(t.get("politician")),
                    "ticker": t.get("ticker"),
                    "asset": t.get("asset_name") or None,
                    "direction": t.get("direction"),
                    "transaction": t.get("transaction_type"),
                    "asset_type": t.get("asset_type"),
                    "owner": t.get("owner"),
                    "amount": t.get("amount_range"),
                    "trade_date": t.get("trade_date"),
                    "disclosure_date": t.get("disclosure_date"),
                    "chamber_source": t.get("source"),
                    "risk_level": t.get("risk_level"),
                    "amends_trade_of": t.get("amends"),
                    "filing_url": t.get("filing_url"),
                }
                for t in cap_rows(items, params["limit"])
            ],
        }
    )


# ── ticker_signal ─────────────────────────────────────────────────────────────


def _signal_row(s: dict[str, Any], *, reasons: bool) -> dict[str, Any]:
    row = {
        "ticker": s.get("ticker"),
        "score": s.get("composite_score"),
        "label": s.get("label"),
        "signal": s.get("signal"),
        "price": s.get("current_price"),
        "sub_scores": s.get("sub_scores"),
        "congress": {
            "buys": s.get("insider_buys"),
            "sells": s.get("insider_sells"),
            "buy_dollars": dollars(s.get("insider_buy_dollars")),
            "sell_dollars": dollars(s.get("insider_sell_dollars")),
        },
        "corporate_insiders": {"buys": s.get("corporate_buys"), "sells": s.get("corporate_sells")},
        "momentum": {"sma20": s.get("sma20"), "sma50": s.get("sma50"), "rsi": s.get("rsi")},
        "window": [s.get("window_start"), s.get("window_end")],
    }
    if reasons:
        row["reasons"] = s.get("reasons", [])
    return row


async def ticker_signal(ticker: str) -> dict[str, Any]:
    """InsiderTrack's composite score for one ticker, with the reasons behind it.

    Score is 0-100: smart money (13F holders) + Congress buying weighted by each
    member's track record + corporate insiders (Form 4) + momentum, minus a risk
    penalty. `label` is the human bucket (e.g. "Strong Watch", "High Risk");
    `signal` is BULLISH / NEUTRAL / BEARISH. Only tickers traded by a tracked
    member of Congress in the window have a score.

    Args:
        ticker: Exact symbol, e.g. NVDA.
    """
    sym = _ticker(ticker)
    if sym is None:
        return client.error("ticker does not look like a symbol", "Try search first")
    data = await client.get("/signals/")
    if client.is_error(data):
        return data
    match = next((s for s in data.get("signals", []) if s.get("ticker") == sym), None)
    if match is None:
        return client.error(
            f"{sym} has no score right now",
            "Scores exist only for tickers a tracked member of Congress traded recently; "
            "congress_trades or insider activity may still have data.",
        )
    return envelope(
        {"score_version": data.get("score_version"), **_signal_row(match, reasons=True)},
        as_of=data.get("computed_at"),
    )


async def top_signals(limit: int = 10, min_score: int | None = None) -> dict[str, Any]:
    """The strongest composite scores right now, highest first (use ticker_signal for the reasons).

    Args:
        limit: Rows to return, 1-25 (default 10).
        min_score: Only tickers scoring at least this (0-100).
    """
    data = await client.get("/signals/")
    if client.is_error(data):
        return data
    rows = [s for s in data.get("signals", []) if s.get("composite_score") is not None]
    if min_score is not None:
        rows = [s for s in rows if s["composite_score"] >= min_score]
    rows.sort(key=lambda s: s["composite_score"], reverse=True)
    return envelope(
        {
            "score_version": data.get("score_version"),
            "scored_tickers": len(rows),
            "signals": [
                _signal_row(s, reasons=False) for s in cap_rows(rows, max(1, min(limit, 25)))
            ],
        },
        as_of=data.get("computed_at"),
    )


# ── cluster_buys ──────────────────────────────────────────────────────────────


async def cluster_buys(days: int = 30, min_buyers: int = 2, limit: int = 25) -> dict[str, Any]:
    """Companies where several corporate insiders bought their own stock on the open market.

    "Cluster buys" — two or more distinct officers, directors or 10% owners
    filing open-market purchases (Form 4 code P) within the window — are one
    of the stronger public signals. Market-wide, not limited to what Congress
    trades. Sorted by total dollars.

    Args:
        days: Look-back window, 1-365 (default 30).
        min_buyers: Minimum distinct insiders buying, 1-10 (default 2).
        limit: Rows to return, 1-100 (default 25).
    """
    days = max(1, min(days, 365))
    min_buyers = max(1, min(min_buyers, 10))
    data = await client.get(
        "/insiders/clusters", {"days": days, "min_buyers": min_buyers, "limit": 200}
    )
    if client.is_error(data):
        return data
    # Some Form 4 filers are unlisted (private BDCs, funds): no symbol to act on.
    listed = [c for c in data.get("items", []) if c.get("ticker") and c["ticker"] != "NONE"]
    return envelope(
        {
            "days": days,
            "min_buyers": min_buyers,
            "clusters": [
                {
                    "ticker": c.get("ticker"),
                    "company": c.get("company"),
                    "buyers": c.get("buyers"),
                    "buys": c.get("buys"),
                    "dollars": dollars(c.get("dollars")),
                    "last_buy": c.get("last_buy"),
                }
                for c in cap_rows(listed, max(1, min(limit, 100)))
            ],
        }
    )


# ── member_track_record ───────────────────────────────────────────────────────


def _windows(w: dict[str, Any] | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for days, row in (w or {}).items():
        out[f"{days}d"] = {
            "n": row.get("n"),
            "win_rate_pct": row.get("win_rate"),
            "avg_return_pct": row.get("avg_return"),
            "avg_excess_vs_spy_pct": row.get("avg_excess"),
            "beat_spy_rate_pct": row.get("beat_spy_rate"),
        }
    return out


def _measured_trade(t: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": t.get("ticker"),
        "trade_date": t.get("trade_date"),
        "disclosure_date": t.get("disclosure_date"),
        "amount": t.get("amount_range"),
        "owner": t.get("owner"),
        "entry_price": t.get("entry_price"),
        "return_pct": {"30d": t.get("r30"), "60d": t.get("r60"), "90d": t.get("r90")},
        "excess_vs_spy_pct": {"30d": t.get("x30"), "60d": t.get("x60"), "90d": t.get("x90")},
    }


async def member_track_record(politician_id: int, recent_trades: int = 10) -> dict[str, Any]:
    """How a member of Congress's disclosed stock buys (and sales) actually performed.

    Every buy is measured from the first close after disclosure at 30/60/90
    days, against SPY over the same days. `weight_in_score` is what that
    record earns the member's trades in the composite score (1.0 = neutral).
    Sales are measured the same way (a good sale is one the stock then fell).

    Args:
        politician_id: From `search`.
        recent_trades: Measured buys to list, 0-50 (default 10).
    """
    record = await client.get(f"/politicians/{politician_id}/track-record")
    if client.is_error(record):
        return record
    member = await client.get(f"/politicians/{politician_id}")
    n = max(0, min(recent_trades, 50))
    sells = record.get("sells") or {}
    buy_rows = cap_rows(record.get("trades", []), n) if n else []
    sell_rows = cap_rows(sells.get("trades", []), n) if n else []
    return envelope(
        {
            "member": _politician(member) if not client.is_error(member) else {"id": politician_id},
            "weight_in_score": None if client.is_error(member) else member.get("skill_factor"),
            "buys": {
                "measured": record.get("evaluated"),
                "windows": _windows(record.get("windows")),
                "recent": [_measured_trade(t) for t in buy_rows],
            },
            "sales": {
                "windows": _windows(sells.get("windows")),
                "recent": [_measured_trade(t) for t in sell_rows],
            },
        }
    )


# ── leaderboard ───────────────────────────────────────────────────────────────


async def leaderboard(min_trades: int = 10, limit: int = 20) -> dict[str, Any]:
    """Members of Congress ranked by how often their stock buys beat SPY at 90 days.

    Only members with at least `min_trades` measured buys are ranked, so a
    lucky single trade does not top the list. `weight_in_score` is the
    multiplier that record earns their trades in the composite score.

    Args:
        min_trades: Minimum measured buys to qualify, 1-200 (default 10).
        limit: Rows to return, 1-50 (default 20).
    """
    min_trades = max(1, min(min_trades, 200))
    data = await client.get("/politicians/leaderboard", {"min_trades": min_trades, "limit": 300})
    if client.is_error(data):
        return data
    return envelope(
        {
            "min_trades": min_trades,
            "ranked": [
                {
                    "rank": r.get("rank"),
                    "member": _politician(r),
                    "buys_measured": r.get("buys_measured"),
                    "beat_spy_rate_pct": r.get("beat_spy_rate"),
                    "weight_in_score": r.get("skill_factor"),
                }
                for r in cap_rows(data.get("ranked", []), max(1, min(limit, 50)))
            ],
        },
        as_of=data.get("as_of"),
    )


# ── signal_outcomes ───────────────────────────────────────────────────────────


async def signal_outcomes(score_version: int | None = None) -> dict[str, Any]:
    """Does a label actually go up? Hit-rates of every score bucket at 30/60/90 days.

    InsiderTrack snapshots every ticker's score daily and fills in what the
    price did 30, 60 and 90 days later. This is the scorecard: per label, how
    many snapshots resolved, how many went up/down/flat, and the win rate.
    Scoring regimes change over time; results are per version (default: the
    current one). Small `total`s mean the regime is young — say so.

    Args:
        score_version: Restrict to one scoring regime; default is the current one.
    """
    data = await client.get("/outcomes/stats", {"score_version": score_version})
    if client.is_error(data):
        return data
    return envelope(
        {
            "score_version": data.get("score_version"),
            "current_version": data.get("current_version"),
            "tracking_since": data.get("tracking_since"),
            "latest_snapshot": data.get("latest_snapshot"),
            "total_snapshots": data.get("total_snapshots"),
            "labels": [
                {
                    "label": row.get("label"),
                    **{
                        w: {
                            "resolved": (row.get(w) or {}).get("total"),
                            "up": (row.get(w) or {}).get("up"),
                            "down": (row.get(w) or {}).get("down"),
                            "flat": (row.get(w) or {}).get("flat"),
                            "win_rate_pct": (row.get(w) or {}).get("win_rate"),
                        }
                        for w in ("d30", "d60", "d90")
                    },
                }
                for row in data.get("labels", [])
            ],
            "versions": data.get("versions", []),
        }
    )


# ── model_desk ────────────────────────────────────────────────────────────────


def _call(c: dict[str, Any]) -> dict[str, Any]:
    return {
        "date": c.get("call_date"),
        "ticker": c.get("ticker"),
        "direction": c.get("direction"),
        "horizon_days": c.get("horizon_days"),
        "confidence": c.get("confidence"),
        "reasoning": clip_text(c.get("reasoning")),
        "price_at_call": c.get("price_at_call"),
        "resolves_on": c.get("resolves_on"),
        "outcome": c.get("outcome"),
        "return_pct": c.get("return_pct"),
        "excess_vs_spy_pct": c.get("excess_pct"),
        "model": c.get("provider"),
    }


async def model_desk(history: int = 0) -> dict[str, Any]:
    """The site's own AI model's morning brief and directional calls — and how they scored.

    Each morning the model reads the day's disclosures and makes 3-5 calls
    (ticker, bullish/bearish, 30/60/90-day horizon, confidence, reasoning).
    Calls are scored at their horizon against SPY exactly like members'
    trades. Treat it as a scorecard of the model, not a forecast.

    Args:
        history: Also return this many past calls, newest first, 0-100 (default 0).
    """
    today = await client.get("/ai-desk/today")
    if client.is_error(today):
        return today
    brief = today.get("brief") or {}
    out: dict[str, Any] = {
        "brief": {
            "date": brief.get("date"),
            "summary": clip_text(brief.get("summary")),
            "model": brief.get("provider"),
        }
        if brief
        else None,
        "todays_calls": [_call(c) for c in cap_rows(today.get("calls", []))],
        "scorecard": today.get("stats"),
    }
    n = max(0, min(history, 100))
    if n:
        past = await client.get("/ai-desk/calls", {"limit": n})
        if not client.is_error(past):
            out["past_calls"] = [_call(c) for c in cap_rows(past.get("items", []), n)]
    return envelope(out, as_of=brief.get("date"))


# ── funds: fund_leaderboard, fund_track_record ────────────────────────────────


async def fund_leaderboard() -> dict[str, Any]:
    """Institutional investors (13F filers) ranked by how their position changes performed vs SPY.

    Each fund's new and increased positions are measured from the day the
    13F became public (up to 45 days after quarter end — the date that
    matters, not the quarter end) at 30/60/90 days against SPY. `window` is
    the longest horizon with data; a fund needs two loaded quarters to be
    measured at all, so early on only a few are ranked and the rest show
    `measured: false`. Use `fund_track_record` for the detail.
    """
    data = await client.get("/whales/leaderboard")
    if client.is_error(data):
        return data
    rows = data.get("items", [])
    ranked = [r for r in rows if r.get("computed") and r.get("window")]
    return envelope(
        {
            "ranked": [
                {
                    "rank": i + 1,
                    "fund": {"id": r.get("id"), "name": r.get("name")},
                    "window_days": r.get("window"),
                    "changes_measured": r.get("n"),
                    "beat_spy_rate_pct": r.get("beat_spy_rate"),
                    "avg_excess_vs_spy_pct": r.get("avg_excess"),
                }
                for i, r in enumerate(cap_rows(ranked))
            ],
            "not_yet_measured": [
                {"id": r.get("id"), "name": r.get("name")}
                for r in rows
                if not (r.get("computed") and r.get("window"))
            ],
        }
    )


def _fund_change(t: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": t.get("ticker"),
        "company": t.get("company"),
        "change": t.get("change"),
        "quarter": t.get("quarter"),
        "position_value": dollars(t.get("value_usd")),
        "public_on": t.get("public_on"),
        "entry_price": t.get("entry_price"),
        "return_pct": {"30d": t.get("r30"), "60d": t.get("r60"), "90d": t.get("r90")},
        "excess_vs_spy_pct": {"30d": t.get("x30"), "60d": t.get("x60"), "90d": t.get("x90")},
    }


async def fund_track_record(holder_id: int, recent_changes: int = 10) -> dict[str, Any]:
    """How one institutional investor's 13F position changes performed vs SPY.

    "Buys" are new and increased positions, "sales" trims and exits
    (measured in the inverted sense: a good sale is one the stock then
    fell). Every change is measured from the 13F's public date — a quarter-
    end snapshot the fund filed up to 45 days later — so this is what a
    person copying the filing could have done, not what the fund did.
    Windows with `n` 0 simply have no resolved data yet.

    Args:
        holder_id: From `fund_leaderboard` or `search`.
        recent_changes: Measured changes to list, 0-50 (default 10).
    """
    record = await client.get(f"/whales/{holder_id}/track-record")
    if client.is_error(record):
        return record
    n = max(0, min(recent_changes, 50))
    buys, sells = record.get("buys") or {}, record.get("sells") or {}
    buy_rows = cap_rows(buys.get("trades", []), n) if n else []
    sell_rows = cap_rows(sells.get("trades", []), n) if n else []
    return envelope(
        {
            "fund_id": holder_id,
            "buys": {
                "measured": buys.get("evaluated"),
                "windows": _windows(buys.get("windows")),
                "recent": [_fund_change(t) for t in buy_rows],
            },
            "sales": {
                "windows": _windows(sells.get("windows")),
                "recent": [_fund_change(t) for t in sell_rows],
            },
        }
    )


# ── watchlist_add (the one write; registered only when the operator enabled it) ──


async def watchlist_add(ticker: str) -> dict[str, Any]:
    """Add a ticker to the site owner's InsiderTrack watchlist.

    The only tool that changes anything. It acts as the owner's own watchlist
    identity on the site (not an admin), so the worst it can do is add a
    symbol to that one list. Say which ticker you added.

    Args:
        ticker: Exact symbol, e.g. NVDA.
    """
    from .config import settings

    sym = _ticker(ticker)
    if sym is None:
        return client.error("ticker does not look like a symbol", "Try search first")
    data = await client.post(
        "/watchlist/", {"email": settings.insidertrack_watchlist_email, "ticker": sym}
    )
    if client.is_error(data):
        return data
    return envelope({"status": data.get("status", "added"), "ticker": sym})


TOOLS = (
    search,
    congress_trades,
    ticker_signal,
    top_signals,
    cluster_buys,
    member_track_record,
    leaderboard,
    signal_outcomes,
    model_desk,
    fund_leaderboard,
    fund_track_record,
)
WRITE_TOOLS = (watchlist_add,)
