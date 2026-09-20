# Changelog

All notable changes to InsiderTrack MCP. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions: [Semantic Versioning](https://semver.org/).

## [Unreleased]

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

[0.1.0]: https://github.com/mrgutierrezmario/insidertrack-mcp/releases/tag/v0.1.0
