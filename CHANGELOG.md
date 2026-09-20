# Changelog

All notable changes to InsiderTrack MCP. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions: [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Project scaffold: MCP server (`mcp` SDK 2.x) with stdio and streamable-HTTP transports,
  bearer-token auth, per-client rate limit, audit log, `/health`.
- `search` tool: members of Congress, tickers and Fed officials by name or symbol.
- Cautious upstream client: timeout, error objects instead of exceptions, detection of the
  app's HTML fallback.
- Docker image, Compose snippet for the InsiderTrack stack, CI (ruff, pytest, image build +
  smoke), Dependabot with auto-merge for patch/minor bumps.
