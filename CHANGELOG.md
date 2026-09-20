# Changelog

All notable changes to InsiderTrack MCP. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions: [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Project scaffold: MCP server (`mcp` SDK 2.x) with stdio and streamable-HTTP transports,
  bearer-token auth, per-client rate limit, audit log, `/health`.
- Nine read-only tools: `search`, `congress_trades`, `ticker_signal`, `top_signals`, `cluster_buys`,
  `member_track_record`, `leaderboard`, `signal_outcomes`, `model_desk` — each tested against a
  recorded response and verified against a live instance.
- Cautious upstream client: timeout, error objects instead of exceptions, detection of the
  app's HTML fallback.
- `watchlist_add`, the one write, registered only when `MCP_ALLOW_WRITES=1` and the owner's
  watchlist e-mail + token are configured; acts as that identity, never as an admin.
- Server mounted at `/mcp` (health at `/mcp/health`) to sit behind a Tailscale serve path rule.
- Docker image, Compose snippet for the InsiderTrack stack, CI (ruff, pytest, image build +
  smoke), Dependabot with auto-merge for patch/minor bumps.
