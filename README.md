# InsiderTrack MCP

An [MCP](https://modelcontextprotocol.io) server for
[InsiderTrack](https://github.com/mrgutierrezmario/insidertrack): let an AI
assistant — Claude Desktop, claude.ai, Claude Code, or any MCP client — ask
who in Congress is buying what, which corporate insiders are clustering,
what a ticker scores and why, and whether those signals actually worked.

**By M.G. Network and Technology Solutions.**

> **v0.2.0** — running in production alongside InsiderTrack: eleven read tools,
> two resources, two prompts, token-gated over the public URL. Connected to
> claude.ai as a custom connector. Design notes in [DESIGN.md](DESIGN.md).

## What it looks like

A question the site cannot answer on any one page — *"Where are several
insiders buying their own stock this month, and did anyone in Congress buy
the same names? How good is that member's record?"* — becomes three tool
calls. Recorded against the live instance on 2026-09-20:

```
cluster_buys(days=30)
  BABA  2 insiders  $25.7M      PMTS  5 insiders  $12.0M
  GME   4 insiders  $21.7M      SBLK  8 insiders  $6.9M
  UBER  2 insiders  $15.3M      NGL   2 insiders  $5.8M   …

congress_trades(ticker="UBER", direction="buy", since="2026-06-01")
  Dan Newhouse (R-WA, House)  $1,001 – $15,000  traded 2026-07-10

member_track_record(politician_id=…)
  89 measured buys · 90-day win rate 43.8% · beat SPY 40.4% of the time
  avg excess vs SPY −2.3 pts · weight in the composite score: 0.9
```

So: one overlap, and the member behind it has a below-market record — the
score already discounts his trades. Claude writes that paragraph; the
server only hands it the facts, each stamped `as_of` and with the disclaimer.

## How it works

InsiderTrack already computes everything — scores, member track records,
cluster buys, 30/60/90-day outcomes — behind an HTTP API. This server is a
small, separately deployed process that exposes a curated set of tools over
that API, each described well enough that a model picks the right one, with
guardrails so a chat cannot hurt the app:

- read-only by construction (one optional write, off by default),
- bearer-token auth and a per-client rate limit over HTTP,
- capped result sizes, errors returned as data the model can recover from,
- one audit line per call,
- no database credentials, no volumes — the container can only reach the app.

## Run it

Locally, as a subprocess for Claude Code (no network, no tokens):

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
claude mcp add insidertrack -e INSIDERTRACK_URL=http://localhost:8013 -- .venv/bin/insidertrack-mcp
```

Over HTTP, inside the InsiderTrack Compose stack: add the service from
[`deploy/compose.snippet.yml`](deploy/compose.snippet.yml) to its
`deploy/compose.yml`, put an `MCP_TOKENS=name:token` line in its
`deploy/.env`, and add a `/mcp` handler to the Tailscale serve config
(Tailscale strips the prefix, so the server itself listens at `/`).

Then connect a client:

| Client | How |
|---|---|
| **claude.ai / Claude Desktop** | Settings → Connectors → *Add custom connector* → URL `https://<host>/mcp`, transport Streamable HTTP, Authentication **No sign-in**, request header `X-API-Key` = the token. (claude.ai keeps the `Authorization` header for its own OAuth, so use `X-API-Key`.) The nine tools appear under *Read-only tools*; set them to *Always allow*. |
| **Claude Code** | `claude mcp add --transport http insidertrack https://<host>/mcp --header "Authorization: Bearer <token>"` |
| **Local, no network** | `claude mcp add insidertrack -e INSIDERTRACK_URL=http://localhost:8013 -- .venv/bin/insidertrack-mcp` |

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"   # make a token
```

## Tools

| Tool | Question it answers |
|---|---|
| `search` | "Who is Pelosi in this system? What's the exact ticker? Which fund is Berkshire?" — ids and symbols for the other tools |
| `congress_trades` | "What did members of Congress do in NVDA since June?" — filter by ticker, member, buy/sell, owner, asset type, dates |
| `ticker_signal` | "What does KMX score, and why?" — the 0–100 composite, sub-scores and written reasons |
| `top_signals` | "What scores highest right now?" — the strongest tickers, no reasons |
| `cluster_buys` | "Where are several insiders buying their own stock?" — market-wide Form 4 clusters |
| `member_track_record` | "How have Pelosi's buys actually done?" — 30/60/90-day returns vs SPY, buys and sales, the weight it earns |
| `leaderboard` | "Which members beat the market most often?" — ranked by 90-day beat-SPY rate |
| `signal_outcomes` | "Does 'Strong Watch' actually go up?" — hit-rates per label per scoring version |
| `model_desk` | "What did the site's model call this morning, and how have its calls scored?" |
| `fund_leaderboard` | "Which 13F funds' position changes actually beat the market?" — measured from the filing's public date, not quarter end |
| `fund_track_record` | "How did Renaissance's new and increased positions do?" — 30/60/90-day returns vs SPY, buys and sales |

All read-only and idempotent (declared as such in the tool annotations),
each capped to a sensible number of rows, dollars pre-formatted, no internal
ids a model cannot use. One optional write, `watchlist_add`, exists only when
the operator sets `MCP_ALLOW_WRITES=1` and gives the server their own
watchlist identity — it never holds an admin credential.

### Resources and prompts

| | |
|---|---|
| `insidertrack://brief/today` | The site's model's morning brief and today's calls, as text |
| `insidertrack://sources/health` | How fresh each data source is, and recent errors — so an answer can say "House data is two days old" |
| prompt `morning_brief` | What changed this week: cluster buys, Congress purchases, top scores, how the model's calls resolved |
| prompt `due_diligence(ticker)` | A one-page note on one ticker, in a fixed order, ending with what the data supports, what it doesn't, and what would change the picture |

Every result carries `as_of` and a disclaimer: InsiderTrack scores public
disclosures; it is a scorecard, not investment advice.

## Development

```bash
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/python -m pytest -q
docker build -f deploy/Dockerfile -t insidertrack-mcp .
```

Tests run against recorded API responses in `tests/fixtures/` — no
InsiderTrack instance needed. CI runs lint, tests and the Docker build on
every push; Dependabot keeps the pins current (patch and minor bumps merge
themselves once CI is green).

## Operations

Nothing to back up — no database, no volumes; tokens live in InsiderTrack's
`.env`, which its nightly backup covers. How it comes back after a reboot,
how to update or rebuild it, rotate tokens, and what to check when it's
down: [`deploy/OPERATIONS.md`](deploy/OPERATIONS.md).

## Versions

The version lives in `VERSION` and is reported by the server on
initialise and at `/health`. See [CHANGELOG.md](CHANGELOG.md).

## License

[PolyForm Noncommercial 1.0.0](LICENSE) — © 2026 M.G. Network and Technology Solutions.
