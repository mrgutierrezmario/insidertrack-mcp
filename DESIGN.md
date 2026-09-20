# InsiderTrack MCP — design

An [MCP](https://modelcontextprotocol.io) server that lets an AI assistant
(Claude Desktop, claude.ai, Claude Code, or any MCP client) ask questions
of a running [InsiderTrack](https://github.com/mrgutierrezmario/insidertrack)
instance: who in Congress is buying what, which insiders are clustering,
what a ticker scores and why, and whether those signals have actually
worked.

Status: **design** (2026-09-20). Nothing built yet.

## 1. What it is, in one paragraph

InsiderTrack already computes everything — scores, track records, cluster
buys, outcomes — behind an HTTP API. This project is a small, separately
deployed server that exposes a **curated set of eight tools** over that
API, described well enough that a model can pick the right one, with
guardrails so that a chat cannot hurt the app. It is read-only except for
one explicit watchlist tool. It ships as one container that joins the
InsiderTrack Compose stack, and reaches the outside world through the
same Tailscale Funnel URL under `/mcp`.

## 2. Decisions

| Decision | Choice | Why |
|---|---|---|
| Data access | **InsiderTrack's HTTP API**, not the database | Scores, track records and clusters are computed in the app (with caching and price-API fan-out); reading tables directly would mean duplicating that logic and drifting from the site. The API is the contract |
| Repo | **Separate** (`insidertrack-mcp`), own CI, own releases | Reads as a third project; the app stays unaware of it; versions independently |
| Language | Python 3.12, official `mcp` SDK (FastMCP), `httpx` | Same language as the app; the SDK's decorators turn a typed function into a tool with a schema |
| Transport | **Streamable HTTP** at `/mcp`, plus **stdio** for local use | HTTP is what claude.ai custom connectors and Claude Desktop remote servers speak; stdio is free with FastMCP and handy for Claude Code on the same machine |
| Auth (client → MCP) | Bearer token, one per client, in `deploy/.env` | The Funnel URL is public; the server must not be. OAuth is the spec's preferred path — v2 if a second user ever needs access |
| Auth (MCP → app) | None needed for reads; the app's admin token only for `watchlist_add` | InsiderTrack's read endpoints are public behind the site-access agreement; the MCP container calls the app on the Docker network (`http://app:8003`), never through the Funnel |
| Writes | **One** tool (`watchlist_add`), off by default (`MCP_ALLOW_WRITES=0`) | Everything valuable is a question. One write proves the pattern without making the server dangerous |
| Result size | Hard caps per tool (rows, characters); dates and dollars pre-formatted | Tool output is context; 500 raw rows help nobody. The model asks again with a narrower filter |
| Disclaimer | In every tool description and in the server instructions | It is a scorecard, not advice — same line the app uses |

## 3. Tools

Names are verbs a person would say. Every tool returns a JSON object with
`as_of` (when the app computed it) and `disclaimer`; errors come back as
`{"error": "...", "hint": "..."}` rather than exceptions, so the model can
recover.

| Tool | Input | Output (capped) | Backed by |
|---|---|---|---|
| `search` | `query` (name or ticker fragment) | matching politicians `{id, name, chamber, party, state}` and tickers | `GET /search?q=` |
| `congress_trades` | `ticker?`, `politician_id?`, `direction?` buy/sell, `owner?`, `asset_type?`, `since?`, `until?`, `limit` ≤ 100 | trades: member, ticker, direction, amount bracket, owner, asset type, trade/disclosure dates, source, amends | `GET /trades/` |
| `ticker_signal` | `ticker` | composite score 0–100, label, signal (BULLISH/NEUTRAL/BEARISH), the four sub-scores with their written reasons, risk penalty, score version | `GET /signals/` (filtered client-side; cached 5 min in the app) |
| `top_signals` | `limit` ≤ 25, `min_score?` | the strongest tickers now, same shape as above but without reasons | `GET /signals/` |
| `cluster_buys` | `days` (1–365, default 30), `min_buyers` (default 2) | tickers with ≥ N distinct insiders buying on the open market: company, buyers, total value, latest date | `GET /insiders/clusters` |
| `insider_transactions` | `ticker`, `days?`, `type?` buy/sell | Form 4 rows: insider, title, code, shares, price, value, dates, source URL | `GET /insiders/` |
| `member_track_record` | `politician_id` | buys and sales measured at 30/60/90 d vs SPY: n, win rate, average excess, the weight it earns in the score; last 20 trades | `GET /politicians/{id}/track-record`, `/trades` |
| `leaderboard` | `min_trades` (default 10), `limit` ≤ 50 | members ranked by 90-day beat-SPY rate | `GET /politicians/leaderboard` |
| `signal_outcomes` | `score_version?`, `window_days?` | hit-rate per label at 30/60/90 d, n per cell — "does Strong Watch go up?" | `GET /outcomes/stats` |
| `model_desk` | `date?` (default today), `include_history` | the morning brief and 3–5 calls with direction, horizon, confidence, reasoning; resolved calls with hit/miss and excess vs SPY | `GET /ai-desk/today`, `/ai-desk/calls` |
| `watchlist_add` *(writes on)* | `ticker` | ok / already there | `POST /watchlist/` with admin token |

That is ten reads and one write; the first cut ships the **eight in bold
below** and adds the rest once they are used:
**search, congress_trades, ticker_signal, cluster_buys, member_track_record,
leaderboard, signal_outcomes, model_desk.**

### Resources

- `insidertrack://brief/today` — the model desk's morning brief as text.
- `insidertrack://sources/health` — per-scraper freshness (OK / stale /
  failing), so the assistant can say "Senate data is three days old" before
  answering.

### Prompts

- `morning_brief` — "Summarise what changed this week: new cluster buys,
  members with notable purchases, top signals, and how last month's calls
  resolved." Calls four tools, one paragraph each.
- `due_diligence(ticker)` — signal, insiders, Congress, track records of
  the members involved, outcomes for that label. One page.

## 4. Guardrails

- Read-only by construction: the client only knows `GET` endpoints unless
  `MCP_ALLOW_WRITES=1`, and then only `POST /watchlist/`.
- Per-token rate limit (60 calls / minute) and a 10-second upstream timeout.
- Output caps: rows per tool as above; free text (reasoning, briefs)
  truncated at 4,000 characters with a marker.
- Input validation from the type hints (dates, enums, ranges) — a bad
  ticker returns `{"error": "Unknown ticker", "hint": "Try search first"}`.
- Audit log: one line per call — timestamp, token name, tool, arguments,
  rows returned, duration — to stdout (Docker collects it) and never the
  token itself.
- The container has no database credentials and no volume; it can only
  reach `app:8003`.

## 5. Deployment

```
insidertrack stack (deploy/compose.yml)
  app        ← FastAPI + UI, :8003
  postgres
  tailscale  ← Funnel: https://<name>.ts.net → app:8003
  mcp        ← NEW: this project, :8100, joins the same network
```

The Funnel forwards one port, so the app's reverse-proxies `/mcp/*` to
`mcp:8100` (a 15-line addition to InsiderTrack's `main.py`, or a path rule
in the Tailscale serve config — the latter keeps the app untouched and is
preferred). Locally, `MCP_TRANSPORT=stdio` runs it as a subprocess for
Claude Code with no network at all.

Config (`deploy/.env`):

```
INSIDERTRACK_URL=http://app:8003
MCP_TOKENS=claude-desktop:<random>,claude-code:<random>
MCP_ALLOW_WRITES=0
INSIDERTRACK_ADMIN_TOKEN=            # only if writes are on
```

## 6. Repository layout

```
insidertrack-mcp/
├── src/insidertrack_mcp/
│   ├── server.py        # FastMCP app: tools, resources, prompts, auth, audit
│   ├── client.py        # httpx wrapper over the InsiderTrack API, caps, errors
│   ├── formatting.py    # dollars, dates, truncation
│   └── config.py        # env → settings
├── tests/
│   ├── test_tools.py    # each tool against a recorded API fixture (respx)
│   ├── test_auth.py     # missing/wrong token → 401; rate limit → 429
│   └── fixtures/        # JSON captured from a real instance, scrubbed
├── deploy/
│   ├── Dockerfile
│   ├── compose.snippet.yml   # the service block to paste into InsiderTrack's compose
│   └── OPERATIONS.md
├── .github/workflows/ci.yml  # ruff + pytest + docker build
├── .github/dependabot.yml
├── pyproject.toml
├── VERSION, CHANGELOG.md, LICENSE (PolyForm Noncommercial), README.md
```

## 7. Plan

| Phase | Deliverable | Done when |
|---|---|---|
| 0 — scaffold (½ day) | repo, pyproject, FastMCP hello-world with `search`, CI green, Dependabot | `claude mcp add` in Claude Code lists the tool and it answers |
| 1 — the eight tools (2–3 days) | tools, client with caps and error shapes, fixtures + tests | every tool has a test; the *due diligence* prompt produces a page for NVDA |
| 2 — deploy (1 day) | Dockerfile, compose snippet, Funnel path, bearer auth, audit log, rate limit | works from Claude Desktop and claude.ai on a phone, over the internet, with a token; no token → 401 |
| 3 — polish (1 day) | resources, prompts, README with a real transcript, v0.1.0 release | LinkedIn post: one screenshot of a question the site alone can't answer |
| 4 — later | writes (`watchlist_add`), OAuth, `insider_transactions` / `top_signals`, a second server for Lecture Notes reusing the scaffold | as needed |

## 8. Open questions

1. **Funnel path vs second Funnel port.** One `/mcp` path on the existing
   URL is cleanest; Tailscale serve supports path-based routing. Verify on
   the Mac before phase 2.
2. **Site-access gate.** InsiderTrack records an agreement per IP; calls
   from the `mcp` container arrive from the Docker network. Confirm the
   read endpoints don't gate on it (they appear not to).
3. **Ticker validation.** Is there a cheap "known tickers" endpoint, or is
   `search` enough? Affects the error hint in `ticker_signal`.
4. **Signals payload size.** `GET /signals/` returns every tracked ticker;
   `ticker_signal` filters one out client-side. Fine for now (cached 5 min
   in the app); a `?ticker=` parameter upstream would be a one-line
   improvement to InsiderTrack if it grows.
