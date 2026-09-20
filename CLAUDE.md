# InsiderTrack MCP — working notes for Claude

Read this before touching anything. It says what is done, what is left,
and — most of all — how to finish this server **without breaking the
InsiderTrack app it reads from**. The app is live, public, on a Mac at home,
and it has scheduled jobs and a data pipeline that this project must never
disturb. Written 2026-09-20 from the state of both repos on that day.

Companion documents: `DESIGN.md` (the decisions and the tool table),
`README.md`, `CHANGELOG.md`. Where this file and DESIGN.md disagree, this
file is newer — fix DESIGN.md.

---

## 1. The two projects, and the line between them

| | InsiderTrack (`../stock-tracker`) | InsiderTrack MCP (this repo) |
|---|---|---|
| What | The site: scrapers, scores, track records, AI Desk, alerts, UI | A server that lets Claude ask the site questions |
| Direction of AI | The **site calls a model** (Gemini today; Ollama wired in, unconfigured) for three jobs: reading scanned paper filings, the daily AI Desk brief, on-demand research notes | **Claude calls the site.** No model runs here. This server never needs, holds or spends the site's AI key |
| Live at | `https://mgnts-stock-tracker.tail3659a6.ts.net` | will be `…/mcp` on the same URL (phase 2) |
| Repo | `github.com/mrgutierrezmario/insidertrack`, public, v1.1.0, branch protection on `main` | `github.com/mrgutierrezmario/insidertrack-mcp` |

**The rule:** this project consumes the app's public read API. It does not
change the app's data, quotas, jobs or schema. If finishing a tool seems to
need a change in the app, stop and list it under §7 ("asks of the app")
instead of making it; the app has its own checkpoint and its own session.

## 2. Standing rules from the owner (apply here too)

- **No attribution trailers on commits** — no `Co-Authored-By`, no tool
  name, nothing. Author is the git user; message only.
- No secrets in git. Tokens live in InsiderTrack's `deploy/.env` (ignored)
  or a local `.env` here (ignored). `.env.example` files carry empty keys.
- Keep the changelog and README true after every feature; keep `VERSION`
  in step with releases.
- Tests run and pass before a commit; CI must stay green on `main`.

## 3. Where the project stands

Done (commits `723e0d3`, `b1e6679`, `b14e25c`):

- Phase 0 — scaffold, `mcp` SDK 2.x, stdio + streamable-HTTP transports,
  bearer auth, per-token rate limit (60/min), audit line per call,
  `/health`, Dockerfile, compose snippet, CI (ruff + pytest + image build),
  Dependabot with auto-merge.
- Phase 1 — nine read tools in `src/insidertrack_mcp/tools.py`: `search`,
  `congress_trades`, `ticker_signal`, `top_signals`, `cluster_buys`,
  `member_track_record`, `leaderboard`, `signal_outcomes`, `model_desk`.
  Each has a recorded fixture and a test; each was verified against the
  live instance.
- The client (`client.py`) has a 10 s timeout, returns `{"error","hint"}`
  objects instead of raising, and detects the app's HTML fallback (see §5).

Not done: phase 2 (deploy behind the Funnel), phase 3 (resources, prompts,
README transcript, v0.1.0), phase 4 (writes, OAuth, extra tools). Also the
README still says "one tool is live" — it is nine; fix it in phase 3.

## 4. What to do next, in order, and why

### Phase 2 — deploy into the InsiderTrack stack

Goal: `https://mgnts-stock-tracker.tail3659a6.ts.net/mcp` answers with a
token and refuses without one, from Claude Desktop and claude.ai.

1. **Verify the Funnel path rule first, on paper, before touching the
   stack.** The app's `deploy/compose.yml` writes a Tailscale `serve.json`
   with one handler, `"/" → http://127.0.0.1:8003`. The plan is a second
   handler `"/mcp" → http://mcp:8100`. Two things to confirm on the Mac
   (they are DESIGN.md open question 1, still open):
   - ~~Tailscale serve does not strip the mount path~~ — **wrong, verified
     live 2026-09-20: it strips it.** `/mcp/health` reaches this server as
     `/health` and `/mcp` as `/`. The server mounts at `/` (`MCP_PATH`).
   - The tailscale container resolves the compose service name `mcp`
     (it is on the stack's default network; the *app* is not a separate
     network member — it shares the tailscale container's netns, which is
     why the app's in-stack address is `tailscale:8003`).
2. **Additions to the InsiderTrack repo** (these are the only app-side
   changes phase 2 needs; keep them to exactly this):
   - `deploy/compose.yml`: paste the service from `deploy/compose.snippet.yml`;
     add the `"/mcp"` handler to the serve.json heredoc.
   - `deploy/.env.example`: `MCP_TOKENS=` with a comment on how to mint one.
   - `deploy/OPERATIONS.md`: a short "MCP" section (how to add/rotate a
     token, how to check `/mcp/health`).
   - `README.md` of the app: one line under integrations pointing here.
   Nothing in `app/`. No new endpoint, no schema change, no scheduler change.
3. **Fix the snippet before pasting it.** It currently passes
   `INSIDERTRACK_ADMIN_TOKEN: ${ADMIN_TOKEN:-}`. There is no such thing:
   the app's admin credential is a password, and its token is an
   **hourly HMAC** of that password (cookie or `X-Admin-Token`), so a static
   env token cannot work and must not be attempted. Remove that line. The
   one planned write (`watchlist_add`) uses the owner's watchlist token
   instead — see §6a.
4. **Deploying without hurting the app.** The stack is (re)started from
   the dev container with `deploy/start.sh` in the app repo, which needs
   `DOCKER_CONFIG` pointing at a dir holding an empty `{}` `config.json`
   (the dev container's Docker creds store is broken). Facts that matter:
   - Changing `serve.json` restarts the tailscale container, and the app
     shares its network namespace, so **the app restarts too**. `start.sh`
     refuses to do this while `GET /jobs/running` reports a backfill /
     re-parse / sync / skill refresh (`--force` overrides — don't). Check
     `/jobs/running` yourself first; the daily jobs run 06:30–09:00 ET and
     the weekly ones Sat 06:00 / Sun 04:30 ET — avoid those windows.
   - After the first full deploy, iterate on this server with
     `docker compose -f deploy/compose.yml up -d --build mcp` **only** —
     that touches nothing else.
   - The mcp service has no volumes and no DB credentials; keep it so.
     Docker Desktop on the Mac refuses bind mounts of dev-container paths
     anyway.
   - The snippet's build context is `../../insidertrack-mcp`, relative to
     the app's `deploy/` dir; that resolves in the dev container
     (`/workspaces/projects/insidertrack-mcp`). Fine — the build context is
     sent by the client.
5. **Prove it**: no token → 401; wrong token → 401; right token → the
   `search` tool answers from claude.ai on a phone. Then a 61st call in a
   minute → 429. Put the transcript in the README (phase 3).

### Phase 3 — polish and v0.1.0

- Resources `insidertrack://brief/today` (from `/ai-desk/today`) and
  `insidertrack://sources/health` (from `/health` → `data`), prompts
  `morning_brief` and `due_diligence(ticker)` as in DESIGN.md §3.
- README: tools table with all nine (plus the new ones below if added), a
  real transcript, setup for Claude Desktop / claude.ai / Claude Code.
- `VERSION` 0.1.0, CHANGELOG section, GitHub release, license check
  (PolyForm Noncommercial, same as the app).

### Phase 4 — optional, only when used

- **Two new read tools the site can now back** (added 2026-09-20, not in
  DESIGN.md yet): `fund_track_record(holder_id)` from
  `GET /whales/{id}/track-record` and `fund_leaderboard` from
  `GET /whales/leaderboard`. See §5 for shapes. Also `whales` from
  `GET /whales/` for ids, or extend `search`.
- `insider_transactions`, `watchlist_add` (design decided — §6a), OAuth.

## 5. The app's API — facts verified against the live instance

- **Trailing slashes matter.** `GET /search/` is the API; `GET /search`
  without the slash falls into the SPA catch-all (`@app.get("/{full_path:path}")`)
  and returns the web page with **200**. The client already detects HTML;
  still, always call paths the way the router declares them.
- **No site-access gate on the API from inside the stack**; the browser
  "agree" gate is a UI thing. Read endpoints need no auth.
- **No rate limit in the app.** This server's 60/min per token is the only
  brake between a chatty client and the app's single uvicorn worker, which
  also runs the scheduler and the scrapers. Keep the limit; keep result caps.
- **Cheap vs. expensive reads.** `/signals/` is cached 5 min in the app
  (all tracked tickers in one payload — filter client-side, don't loop).
  `/politicians/{id}/track-record` and `/whales/{id}/track-record` are
  cached (6 h / 12 h) but a **cold** one fans out to the price API for
  every ticker the member/fund touched — seconds, sometimes tens. Don't
  build a tool that walks all members' track records; use
  `/politicians/leaderboard` and `/whales/leaderboard`, which read the
  caches and never compute.
- Routers (prefixes): `/access /analysis /ai /fed /alerts /earnings /config
  /settings /filings /news /ai-desk /outcomes /market /politicians /insiders
  /search /signals /simulator /whales /watchlist /trades`.
- Shapes the new tools would need:
  - `GET /whales/leaderboard` → `{"items": [{id, name, computed, window: 30|60|90|null,
    n, beat_spy_rate, avg_excess}]}`. `window` is the longest horizon with
    data; only funds with two loaded quarters have one (4 of 21 today; the
    rest join after the Q3 13F sync, mid-November 2026). `n < 5` rows are
    hidden on the site — do the same.
  - `GET /whales/{id}/track-record` → `{holder_id, buys: {evaluated, windows:
    {"30"|"60"|"90": {n, avg_return, median_return, win_rate, avg_excess,
    beat_spy_rate}}, trades: [{position_id, ticker, company, change, quarter,
    value_usd, public_on, entry_date, entry_price, r30, r60, r90, x30, x60,
    x90}]}, sells: {same, inverted sense}, skipped_demo}`. "public_on" is the
    real SEC filing date — the point of the feature; say so in the tool
    description (13F = quarter-end snapshot, public up to 45 days later).
  - `GET /ai-desk/today` → `{brief: {date, summary, provider}|null, calls: [ModelCall], stats}`;
    `GET /ai-desk/calls?limit=` → `{items: [ModelCall], stats}`. A `ModelCall`
    has `direction`, `horizon_days`, `confidence`, `reasoning`, `outcome`
    (`hit|miss|null`), `return_pct`, `spy_return_pct`, `excess_pct`,
    `resolves_on`. First brief was 2026-09-20; first resolved call is
    2026-10-20 — until then `stats.resolved` is 0 and that is correct, not
    a bug.
  - `GET /trades/` is paginated (`limit ≤ 500`, `offset`, `has_more`) and
    filterable by `ticker`, `direction`, `owner`, `asset_type`,
    `politician_id`, `since`, `until`. Rows carry `filing_url`,
    `ai_confidence` (paper rows only), `amends`.
- **Score version is 4.** `signal_outcomes` should default to the current
  version; older snapshots are not comparable and the app's
  `/outcomes/stats` already defaults that way.

## 6. Endpoints this server must never call

All of these either cost the owner money/quota, mutate data, or kick off a
job on a single-worker server. They are admin-gated in the app, but the
rule here is stronger: do not implement a tool for them at all.

- `/ai/*` — research notes on the **site's** AI key (`AI_DAILY_CAP` 150/day
  of the same quota the paper readings need). If a user wants a written
  note, Claude writes it from the data the tools return.
- `POST /ai-desk/generate` — one daily model call; regenerating burns quota
  and overwrites the day's calls.
- `POST /trades/sync`, `/trades/backfill`, `/trades/{id}/reread`,
  `DELETE /trades/{id}`, `POST /whales/sync`, `POST /insiders/sync`,
  `POST /alerts/run`, anything under `/settings`, `/config`, `/access/admin`.
- `POST /watchlist/` with an **admin** credential — there is no such path.
  The watchlist is keyed by e-mail with a per-e-mail bearer token. The
  decided design for the one write is in §6a.

### 6a. `watchlist_add` — decided design (owner's decision, 2026-09-20)

The MCP carries the **owner's own watchlist credentials**; nothing admin.

- How the app works: the first `POST /watchlist/` `{email, ticker}` for a
  new e-mail mints a bearer token and returns it **once** as `token`;
  every later call sends `Authorization: Bearer <token>` with the same
  `{email, ticker}` body. Responses: added / already watching. There is
  one token per e-mail; the site's **recover** flow (Settings → e-mails
  a new token) *replaces* it.
- Config, in the app's `deploy/.env` (never in git):
  ```
  MCP_ALLOW_WRITES=1                    # default 0 = the tool is not even registered
  INSIDERTRACK_WATCHLIST_EMAIL=<owner's watchlist e-mail>
  INSIDERTRACK_WATCHLIST_TOKEN=<that e-mail's token>
  ```
  The token is the value the owner's browser already holds —
  `localStorage["insidertrack_watchlist_token"]` on the site — or a fresh
  one from the recover flow. If recover is ever run again, update `.env`.
- Compose snippet: **remove** `INSIDERTRACK_ADMIN_TOKEN: ${ADMIN_TOKEN:-}`
  and pass the two variables above (`${INSIDERTRACK_WATCHLIST_EMAIL:-}`,
  `${INSIDERTRACK_WATCHLIST_TOKEN:-}`).
- Tool: `watchlist_add(ticker)` → `POST /watchlist/` with the bearer and
  `{email: <env>, ticker}`; return `{"status": "added"|"already_watching",
  "ticker"}`; on 401 return `{"error": "watchlist token rejected",
  "hint": "token was replaced by a recover — update INSIDERTRACK_WATCHLIST_TOKEN"}`.
  Registered only when `MCP_ALLOW_WRITES=1` **and** both variables are set;
  otherwise the server stays read-only by construction. Audit-log it like
  every other call. Never log the token.
- Blast radius if the MCP token leaks: someone can add tickers to the
  owner's watchlist. Acceptable; that is why the write is this one.
- Not doing: one watchlist per MCP client (only matters with a second
  user), any admin-side "add to any watchlist" endpoint (would put the
  admin password in the MCP).

## 7. Asks of the app (do not make these changes here; list them)

Things that would make this server nicer and belong in the app's own
backlog. None blocks phases 2–3.

- `GET /signals/?ticker=` (DESIGN.md open question 4) — avoids pulling the
  whole signal set for one ticker. One-line change; only worth it if
  `ticker_signal` gets heavy use.
- A "known tickers" endpoint (open question 3). Today `search` is enough.
- `/mcp` path rule in the app's serve.json — this **is** phase 2 step 2 and
  is the one app-side change this project is allowed to make.

## 8. Gotchas that have already cost time

- `ugrep` is aliased over `grep` in the dev container; `rg` is absent.
- Backend tests for the **app** can't run natively (dev container is
  Python 3.14, pinned deps have no wheels) — they run inside the app image.
  This repo is Python 3.12 with its own `.venv`; `.venv/bin/pytest` works
  natively. Don't mix the two.
- The app's `main` is protected (CI checks required; admin may push). Push
  small commits; each must pass backend/frontend/image CI.
- Two Claude sessions were working in the app repo at once on 2026-09-20
  and one swept the other's files into a commit with `git add -A`. Stage
  by file name.

## 9. Definition of "done" for this project (v0.1.0)

- `/mcp` on the public URL, token-gated, rate-limited, audit-logged.
- Nine read tools + two resources + two prompts, each tested, README true.
- Zero changes to the app beyond the three deployment files in §4.2.
- The app's `/health` still reports `errors_24h.count: 0` a day after the
  MCP went live, and its scheduled jobs ran on time (Admin → Data sources
  all OK). That last line is the real test that nothing got messed up.
