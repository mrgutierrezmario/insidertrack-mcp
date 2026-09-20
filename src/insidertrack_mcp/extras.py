"""Resources and prompts — the parts of the MCP spec that are not tools.

Resources are things a client can *read* without arguments (today's brief,
the scrapers' health); prompts are reusable question templates that tell the
model which tools to call and in what order.
"""

from __future__ import annotations

from . import client
from .formatting import clip_text

DISCLAIMER_LINE = (
    "Close with one line: InsiderTrack scores public disclosures; "
    "this is a scorecard, not investment advice."
)


# ── Resources ─────────────────────────────────────────────────────────────────


async def brief_today() -> str:
    """Today's Model Desk brief as plain text (or a note that there is none yet)."""
    data = await client.get("/ai-desk/today")
    if client.is_error(data):
        return f"Unavailable: {data['error']}"
    brief = data.get("brief")
    if not brief:
        return "No brief yet today (it is written each morning around 08:30 ET)."
    lines = [f"InsiderTrack Model Desk — {brief.get('date')} (model: {brief.get('provider')})", ""]
    lines.append(clip_text(brief.get("summary")) or "")
    calls = data.get("calls") or []
    if calls:
        lines += ["", "Calls:"]
        for c in calls:
            lines.append(
                f"- {c.get('ticker')}: {c.get('direction')} over {c.get('horizon_days')} days, "
                f"confidence {c.get('confidence')}, resolves {c.get('resolves_on')}"
            )
    return "\n".join(lines)


async def sources_health() -> str:
    """Freshness of every data source, so an answer can say how current the data is."""
    data = await client.get("/health")
    if client.is_error(data):
        return f"Unavailable: {data['error']}"
    sources = (data.get("data") or {}).get("sources") or {}
    lines = [
        f"InsiderTrack {data.get('version')} — overall {data.get('status')}; "
        f"data pipeline {(data.get('data') or {}).get('status')}; "
        f"errors in the last 24 h: {(data.get('errors_24h') or {}).get('count')}",
        "",
    ]
    for key, s in sources.items():
        lines.append(
            f"- {s.get('label', key)}: {s.get('status')}; last success {s.get('last_success_at')}; "
            f"last new rows {s.get('last_new_rows_at')}"
            + (f"; error: {s.get('last_error')}" if s.get("last_error") else "")
        )
    return "\n".join(lines)


# ── Prompts ───────────────────────────────────────────────────────────────────


def morning_brief() -> str:
    """What changed this week across Congress, insiders, scores and the model's calls."""
    return (
        "Give me InsiderTrack's morning brief. Use the tools in this order and write one short "
        "paragraph for each:\n"
        "1. cluster_buys(days=7) — new insider cluster buys this week; name the companies "
        "and dollars.\n"
        "2. congress_trades(since=<7 days ago>, direction='buy', limit=25) — notable purchases by "
        "members; group by member, mention brackets, flag anything with risk_level HIGH.\n"
        "3. top_signals(limit=5) — the strongest scores now, with the label of each.\n"
        "4. model_desk(history=10) — today's calls, and how the resolved ones scored.\n"
        "Then read the resource insidertrack://sources/health and say how fresh the data is in one "
        f"line. {DISCLAIMER_LINE}"
    )


def due_diligence(ticker: str) -> str:
    """One page on a ticker: score and reasons, insiders, Congress, members' records, outcomes."""
    sym = ticker.strip().upper()
    return (
        f"Build a one-page due-diligence note on {sym} from InsiderTrack, in this order:\n"
        f"1. ticker_signal('{sym}') — the composite score, label, signal and the written reasons. "
        "If it has no score, say why and continue with what is available.\n"
        f"2. congress_trades(ticker='{sym}', limit=25) — who in Congress traded it, which "
        "direction, when, what bracket, self or spouse.\n"
        "3. For each distinct member with a buy in step 2 (at most 3), member_track_record(id) — "
        "how their past buys did vs SPY and the weight they carry in the score.\n"
        "4. cluster_buys(days=90) — note whether this ticker appears (insiders buying their own "
        "stock) and the dollars.\n"
        "5. signal_outcomes() — the hit-rate of this ticker's label at 30/60/90 days, and how "
        "many snapshots that rests on; if few, say the regime is young.\n"
        "Finish with three bullets: what the data supports, what it does not, and what would "
        f"change the picture. {DISCLAIMER_LINE}"
    )
