# InsiderTrack MCP

An [MCP](https://modelcontextprotocol.io) server for
[InsiderTrack](https://github.com/mrgutierrezmario/insidertrack): let an AI
assistant — Claude Desktop, claude.ai, Claude Code, or any MCP client — ask
who in Congress is buying what, which corporate insiders are clustering,
what a ticker scores and why, and whether those signals actually worked.

**By M.G. Network and Technology Solutions.**

> Status: the nine read tools work end to end against a live instance.
> Remote deployment (bearer tokens over the Funnel) is next; see [DESIGN.md](DESIGN.md).

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
`deploy/.env`, and forward `/mcp` on the Funnel. Clients connect to
`https://<your-funnel-host>/mcp` with `Authorization: Bearer <token>`.

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"   # make a token
```

## Tools

| Tool | Question it answers |
|---|---|
| `search` | "Who is Pelosi in this system? What's the exact ticker?" — ids and symbols for the other tools |
| `congress_trades` | "What did members of Congress do in NVDA since June?" — filter by ticker, member, buy/sell, owner, asset type, dates |
| `ticker_signal` | "What does KMX score, and why?" — the 0–100 composite, sub-scores and written reasons |
| `top_signals` | "What scores highest right now?" — the strongest tickers, no reasons |
| `cluster_buys` | "Where are several insiders buying their own stock?" — market-wide Form 4 clusters |
| `member_track_record` | "How have Pelosi's buys actually done?" — 30/60/90-day returns vs SPY, buys and sales, the weight it earns |
| `leaderboard` | "Which members beat the market most often?" — ranked by 90-day beat-SPY rate |
| `signal_outcomes` | "Does 'Strong Watch' actually go up?" — hit-rates per label per scoring version |
| `model_desk` | "What did the site's model call this morning, and how have its calls scored?" |

All read-only and idempotent (declared as such in the tool annotations),
each capped to a sensible number of rows, dollars pre-formatted, no internal
ids a model cannot use.

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

## Versions

The version lives in `VERSION` and is reported by the server on
initialise and at `/health`. See [CHANGELOG.md](CHANGELOG.md).

## License

[PolyForm Noncommercial 1.0.0](LICENSE) — © 2026 M.G. Network and Technology Solutions.
