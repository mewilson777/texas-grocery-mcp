# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

An MCP (Model Context Protocol) server, built on FastMCP, that lets an LLM shop HEB (a Texas grocery chain) — search stores, search/inspect products, and manage the authenticated session HEB's site requires. It talks to HEB's *unofficial* web endpoints (Next.js SSR pages and a GraphQL API with persisted query hashes), not a public API, so a lot of the code exists to survive HEB's bot detection (Incapsula/reese84) and to degrade gracefully when it can't get past it.

## Commands

```bash
# Install (editable, with dev tools)
pip install -e ".[dev]"
playwright install chromium   # needed for auth/browser_refresh.py and auth/browser_session.py

# Lint
ruff check src

# Type check (strict mode — see [tool.mypy] in pyproject.toml)
mypy src

# Run the server directly
texas-grocery-mcp        # console script from [project.scripts], or:
python -m texas_grocery_mcp.server
```

Note: `main()` runs `mcp.run(transport="streamable-http", host="127.0.0.1", port=3000)` — **not** stdio. A stdio-style MCP client config (`"command": "uvx"`) will not work against it as written.


There is currently no test suite in this repo (removed in commit `73150ea`, "Remove unit tests"); `pytest`/`respx` still appear in `uv.lock` as leftovers from before that removal but are not in `pyproject.toml`'s `dev` extra. Don't assume `tests/` exists or invent test commands. CI runs `ruff check src` and `mypy src` only.

## Architecture

### Request flow

`server.py` builds a `FastMCP` instance and registers tool functions from `tools/{store,product,session}.py` directly with `mcp.tool(...)`. Tools are thin: they pull a shared `HEBGraphQLClient` via `StateManager.get_graphql_client_sync()` (`state.py`), delegate to it, and shape the response dict. Cross-request state (default store, cached stores from a search, pending login flow) lives in `state.py`'s `StateManager`, which mixes `contextvars` (per-request store override) with a module-level dict guarded by an `asyncio.Lock` (shared across requests).

### The HEB client (`clients/graphql.py`, ~1900 lines — the core of the project)

`HEBGraphQLClient` has two data-fetching strategies and always tries the cheaper/more-authenticated one first, falling back on failure:

1. **Persisted GraphQL queries** (`PERSISTED_QUERIES` dict of query-name → hash) — fast, used for store search and store selection.
2. **SSR scraping** — fetches HEB's Next.js server-rendered pages and parses the embedded `__NEXT_DATA__`/`__NEXT_F` JSON (`_search_products_ssr` → `_parse_ssr_products` → `_parse_ssr_product_item` for search; `_get_product_details_ssr` for details) — used for authenticated product search, since it returns full pricing/inventory that the public GraphQL surface doesn't.
3. **Typeahead fallback** — when authenticated SSR search fails or no auth cookies exist, falls back to HEB's autocomplete endpoint and returns suggestion names as placeholder `Product` records (`price: 0.0`, no real `product_id`). Gated by `settings.typeahead_fallback_enabled` (off by default) — when off, a failed search returns zero products with a `fallback_reason` instead of these fake placeholders.

`search_products` and `search_stores` both record every attempt (`ProductSearchAttempt`/`SearchAttempt` in `models/`) and return them in the result so callers can see exactly which query variations and methods were tried. `_detect_security_challenge` inspects HTML for WAF/CAPTCHA markers; when it fires, the client stops trying more variations immediately (further requests would just waste them) and surfaces `security_challenge_detected` plus manual Playwright recovery instructions.

Persisted query hashes and SSR parsing are both reverse-engineered against HEB's current frontend build and will break silently when HEB ships changes — that's the expected failure mode driving most bugfix commits in this repo (see recent commits touching `graphql.py` for store-search/typeahead updates).

### Auth (`auth/`) — the hard problem this project solves

HEB session state is a Playwright `storage_state`-shaped JSON at `settings.auth_state_path` (default `~/.texas-grocery-mcp/auth.json`): a `cookies` list plus an `origins` list carrying localStorage per-origin (`find_heb_origin` is the one accessor for that — never index `origins[0]`). Three cookies matter: `sat`/`sst`/`JSESSIONID` for login, plus a `reese84` bot-detection token (in a cookie or in localStorage with a `renewTime`) that expires independently of login and is required for API calls to succeed even when logged in.

Several ways to populate that file, in `auth/`:
- `session.py` — reads/writes the auth file, computes `SessionStatus` (time remaining on the reese84 token, `needs_refresh`/`refresh_recommended`), and the `@ensure_session` decorator that auto-refreshes before a tool runs — applied to `store_change` *and* all three product tools. Note what this means: it can return a `LOGIN_REQUIRED`/`HUMAN_ACTION_REQUIRED` dict **instead of** running the tool, so "product search works unauthenticated" only holds when no auth state file exists at all (`auto_refresh_session_if_needed` returns `None` early in that case). A *stale* file can block product search.
- `browser_refresh.py` — drives an embedded Playwright browser (optional `[browser]` extra) to log in / refresh in ~10-15s; supports headless auto-login with saved `credentials.py` creds, and headed mode with a human-in-the-loop CAPTCHA/2FA/WAF handoff (screenshot + `status: "human_action_required"` returned to the caller — see `MCP_INSTRUCTIONS` in `server.py` for the exact protocol).
- `browser_session.py` — **read this module's docstring before touching session/auth code.** It documents a load-bearing, non-obvious finding: HEB's WAF appears to bind trust to the *live browser connection* that logged in, not to the cookie/localStorage values themselves. Serializing `storage_state` to disk and replaying it into a fresh `httpx` client or a new Playwright browser gets 401'd even with byte-identical cookies. The only approach that works reliably is keeping the one browser page that logged in alive and routing subsequent calls through it (`AuthenticatedBrowserSession.adopt`), rather than closing and recreating it. `load_storage_state_without_device_id` strips Incapsula's own device-identity cookies (`incap_ses_*`, `visid_incap_*`) on load so a fresh browser doesn't inherit a possibly-flagged device fingerprint.
- `cookies_txt.py` — alternate manual path: import a Netscape `cookies.txt` export (from a real human-driven browser session) and translate it into the same storage-state shape, merging rather than clobbering existing localStorage. Preferred over scripted login for avoiding fingerprinting when scripted login is unreliable.
- `credentials.py` — OS keyring first, Fernet-encrypted file fallback (0o600), for optional auto-login.
- `browser_fingerprint.py` — the single source of the UA + Client Hints pair used by both Playwright launches and httpx. Read its docstring before touching any header: Playwright's `user_agent=` option rewrites *only* the UA string while `sec-ch-ua` still comes from the real binary, so overriding the UA to claim a different brand/version/OS **creates** the mismatch it looks like it's hiding. Prefer the real `chrome` channel; never claim a brand the running binary isn't.

`utils/secure_file.py` is the shared "write JSON with owner-only permissions" helper — auth state and credentials must go through it, not raw `json.dump`.

### Geocoding (`services/geocoding.py`)

`store_search` takes a free-text address, so it geocodes via Nominatim (OpenStreetMap) before hitting HEB. Two constraints: Nominatim blocks custom app names without real contact info, so `USER_AGENT` is deliberately set to a curl string; and bare zip codes are detected by regex and handled separately from full addresses. It's the only outbound dependency that isn't HEB.

### Reliability (`reliability/`)

Generic, dependency-free-of-the-rest-of-the-app primitives composed inside `HEBGraphQLClient.__init__`: `CircuitBreaker` (per-client, name `"heb_api"`), `Throttler` (separate configs/instances for SSR vs GraphQL traffic — SSR is throttled harder since it's scraping), `TTLCache` (24h product-details cache), and `with_retry`. All tunables are `Settings` fields (`utils/config.py`) — e.g. `max_concurrent_ssr_searches`, `min_ssr_delay_ms`, `circuit_breaker_threshold` — so behavior changes should go through settings/env vars rather than new hardcoded constants.

### Config & logging

`utils/config.py`'s `Settings` (pydantic-settings, reads `.env`) is the single source of truth for tunables; get it via the cached `get_settings()`, don't construct `Settings()` directly. `observability/logging.py` configures structlog to emit JSON **to stderr** — stdout is reserved for the MCP protocol, so never `print()` or log to stdout in this codebase.

### Adding a new MCP tool

Write the function in the relevant `tools/*.py` (plain async/sync function returning a `dict[str, Any]`, params as `Annotated[..., Field(description=...)]` for schema generation), then register it explicitly in `server.py` with `mcp.tool(annotations={"readOnlyHint": True})(...)` (read-only) or `mcp.tool()(...)` (mutating) — there's no auto-discovery. If the tool requires a valid HEB session, wrap it with `@ensure_session` from `auth/session.py`.
