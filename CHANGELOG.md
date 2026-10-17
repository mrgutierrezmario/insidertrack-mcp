# Changelog

All notable changes to InsiderTrack MCP. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions: [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- `late_filers`: members of Congress ranked by trades disclosed more than 45 days after they
  happened (the STOCK Act's outer deadline), all history or the last N days, with share late,
  typical and longest delay, and the worst filing's link. Needs InsiderTrack's
  `GET /politicians/late-filers` (2026-10-16).
- `signal_outcomes` reports each label against SPY over the same trading days: average return,
  average excess in percentage points, and how often it beat SPY (`avg_excess_vs_spy_pts`,
  `beat_spy_rate_pct`). A raw win rate in a rising market says little; these say whether a
  label has an edge. Needs InsiderTrack's `/outcomes/stats` from 2026-10-16 or later; older
  instances return `null` for the new fields.

## [0.2.0] — 2026-09-20

### Added
- `fund_leaderboard` and `fund_track_record`: 13F institutional investors ranked and measured
  the same way as members — from the filing's public date at 30/60/90 days vs SPY. Funds without
  two loaded quarters are listed as not yet measured (most join after the Q3 sync, November 2026).
- `search` also matches 13F fund names, so fund ids are findable.

### Fixed
- HTTP transport is stateless: a server restart or a client that drops its session id no longer
  fails every later call with "Missing session ID".

## [0.1.0] — 2026-09-20

First release: in production next to InsiderTrack, connected to claude.ai.

### Added
- Resources `insidertrack://brief/today` and `insidertrack://sources/health`; prompts
  `morning_brief` and `due_diligence(ticker)`.
- `X-API-Key` accepted alongside `Authorization: Bearer` (claude.ai custom connectors reserve the
  Authorization header); case-insensitive `Bearer`; `name:token` form forgiven.
- Project scaffold: MCP server (`mcp` SDK 2.x) with stdio and streamable-HTTP transports,
  bearer-token auth, per-client rate limit, audit log, `/health`.
- Nine read-only tools: `search`, `congress_trades`, `ticker_signal`, `top_signals`, `cluster_buys`,
  `member_track_record`, `leaderboard`, `signal_outcomes`, `model_desk` — each tested against a
  recorded response and verified against a live instance.
- Cautious upstream client: timeout, error objects instead of exceptions, detection of the
  app's HTML fallback.
- `watchlist_add`, the one write, registered only when `MCP_ALLOW_WRITES=1` and the owner's
  watchlist e-mail + token are configured; acts as that identity, never as an admin.
- Mount path configurable (`MCP_PATH`, default `/`): Tailscale serve strips its handler prefix,
  so publicly the server is `/mcp` and `/mcp/health` while it sees `/` and `/health`.
- Docker image, Compose snippet for the InsiderTrack stack, CI (ruff, pytest, image build +
  smoke), Dependabot with auto-merge for patch/minor bumps.

[0.2.0]: https://github.com/mrgutierrezmario/insidertrack-mcp/releases/tag/v0.2.0
[0.1.0]: https://github.com/mrgutierrezmario/insidertrack-mcp/releases/tag/v0.1.0
