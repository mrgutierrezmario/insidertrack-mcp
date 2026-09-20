# Operator runbook — InsiderTrack MCP

The short version: **this server has nothing to back up.** It holds no
database, no volumes and no state; every answer comes from InsiderTrack's
API at request time. Its only secrets — the client tokens — live in
InsiderTrack's `deploy/.env`, which InsiderTrack's nightly backup already
includes. Losing this container costs nothing; rebuilding it takes a minute.

All commands run on the server, from the **InsiderTrack** repository folder
(the service is part of that Compose stack).

## Nothing to do

| What | When | How you'd know it failed |
|---|---|---|
| Restart after a crash or reboot (`restart: unless-stopped`) | always | claude.ai says the connector can't be reached |
| Dependabot patch/minor updates (auto-merged when CI passes) | Mondays | GitHub email per PR |

## After a reboot

Docker Desktop starts at sign-in and brings the whole InsiderTrack stack up,
`mcp` included. Nothing to do. To check:

```bash
docker compose -f deploy/compose.yml ps mcp          # "healthy"
curl -s https://<host>/mcp/health                     # {"status":"ok",...}
docker compose -f deploy/compose.yml exec tailscale tailscale funnel status   # lists / and /mcp
```

## Update to a new release

```bash
git -C ../insidertrack-mcp pull
docker compose -f deploy/compose.yml up -d --build --no-deps mcp
```

`--no-deps` matters: without it Compose re-runs the stack's one-shot config
writer, and a mid-write reload once dropped the `/mcp` handler. Nothing else
restarts; the app and its data are untouched.

## Rebuild from nothing (the "restore")

There is no data to restore. On a new machine, after InsiderTrack itself has
been restored (`deploy/restore.sh --from-remote latest` in that repo):

```bash
git clone https://github.com/mrgutierrezmario/insidertrack-mcp ../insidertrack-mcp
docker compose -f deploy/compose.yml up -d --build --no-deps mcp
```

The tokens come back with InsiderTrack's `deploy/.env`. If that file was
lost, mint new ones and update the clients (below).

## Tokens

- **Add or rotate**: edit `MCP_TOKENS` in InsiderTrack's `deploy/.env`
  (`name:token,name2:token2`; mint with
  `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`), then
  `docker compose -f deploy/compose.yml up -d --no-deps mcp`.
- **Revoke**: remove the pair and restart the same way. Every client using
  that token gets 401 from then on.
- **Where clients hold it**: claude.ai → Settings → Connectors → the
  connector → request header `X-API-Key`; Claude Code → `claude mcp list`.

## When it's down

1. `curl -s https://<host>/health` — if InsiderTrack itself is down, fix
   that first (its runbook); the MCP only relays.
2. `docker compose -f deploy/compose.yml ps mcp` — not running or unhealthy →
   `docker compose -f deploy/compose.yml logs --tail=50 mcp`, then
   `docker compose -f deploy/compose.yml up -d --no-deps mcp`.
3. `tailscale funnel status` (command above) missing `/mcp` →
   `docker compose -f deploy/compose.yml run --rm --no-deps tailscale-config`.
4. Reachable but every call is 401 → the client's token no longer matches
   `MCP_TOKENS`; the container log line says whether the header arrived and
   how long the token was (never the token itself).
5. "Missing session ID" from a client → should not happen since the server
   went stateless (v0.1.1); if it does, rebuild the image from `main`.

## Where things live

| | |
|---|---|
| Tokens | InsiderTrack `deploy/.env`, `MCP_TOKENS` |
| Service definition | InsiderTrack `deploy/compose.yml`, service `mcp` (template: `deploy/compose.snippet.yml` here) |
| Funnel route | InsiderTrack `deploy/compose.yml`, the `serve.json` heredoc |
| Log (one line per tool call) | `docker compose -f deploy/compose.yml logs mcp` |
| Version running | `/mcp/health`, or the server's `initialize` reply |
