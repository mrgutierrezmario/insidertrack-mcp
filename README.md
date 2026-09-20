# InsiderTrack MCP

An [MCP](https://modelcontextprotocol.io) server for
[InsiderTrack](https://github.com/mrgutierrezmario/insidertrack): let an AI
assistant — Claude Desktop, claude.ai, Claude Code, or any MCP client — ask
who in Congress is buying what, which corporate insiders are clustering,
what a ticker scores and why, and whether those signals actually worked.

**By M.G. Network and Technology Solutions.**

> Status: early. One tool (`search`) is live end to end; the rest are
> specified in [DESIGN.md](DESIGN.md) and arrive in the next releases.

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
| *(next)* `congress_trades`, `ticker_signal`, `cluster_buys`, `member_track_record`, `leaderboard`, `signal_outcomes`, `model_desk` | see [DESIGN.md](DESIGN.md) |

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
