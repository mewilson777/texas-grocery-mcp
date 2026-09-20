# 🛒 Texas Grocery MCP

[![PyPI version](https://badge.fury.io/py/texas-grocery-mcp.svg)](https://pypi.org/project/texas-grocery-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/mgwalkerjr95/texas-grocery-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/mgwalkerjr95/texas-grocery-mcp/actions/workflows/ci.yml)

> 🤖 Let AI do your grocery shopping! An MCP server that connects Claude to H-E-B grocery stores.

**Search products and more — all through natural conversation.**

⚠️ This project is **not affiliated with H-E-B**. It uses unofficial web APIs and browser automation against HEB.com; use responsibly and ensure your usage complies with applicable terms and laws.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🏪 **Store Search** | Find HEB stores by address or zip code |
| 🔍 **Product Search** | Search products with pricing and availability |
| 📋 **Product Details** | Ingredients, nutrition facts, allergens, warnings |
| 🍪 **Cookie Import** | Authenticate from your own browser session in one paste |

> **On authentication:** HEB runs aggressive bot detection, and sessions
> established by automated browsers get blocked or rejected routinely. The
> reliable path is importing cookies from your own real browser session - see
> [Session Management](#-session-management). An embedded-browser auto-refresh
> exists (`session_refresh`) but is best-effort at most.

---

## 📦 Installation

### Quick Start

```bash
pip install texas-grocery-mcp
```

### Full Installation (Recommended) 🚀

```bash
pip install texas-grocery-mcp[browser]
playwright install chromium
```

This enables **fast auto-refresh** (~15 seconds) using an embedded browser.

### Optional: Playwright MCP

Not required. If the embedded browser isn't installed, `session_refresh`
degrades to returning a list of [Playwright
MCP](https://github.com/microsoft/playwright-mcp) commands for your agent to
run instead:

```bash
npm install -g @playwright/mcp
```

The recommended cookie-import workflow needs neither of these.

---

## ⚙️ Configuration

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["@anthropic-ai/mcp-playwright"]
    },
    "heb": {
      "command": "uvx",
      "args": ["texas-grocery-mcp"],
      "env": {
        "HEB_DEFAULT_STORE": "590"
      }
    }
  }
}
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `HEB_DEFAULT_STORE` | Default store ID | None |
| `TYPEAHEAD_FALLBACK_ENABLED` | See note below | `false` |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, or `ERROR` (logs go to stderr) | `INFO` |
| `AUTO_REFRESH_ENABLED` | Auto-refresh the session before authenticated tools run | `true` |
| `AUTO_REFRESH_THRESHOLD_HOURS` | Refresh when less than this much token life remains | `0.05` (3 min) |
| `AUTO_REFRESH_ON_STARTUP` | Refresh on server startup | `false` |
| `THROTTLING_ENABLED` | Global request throttling | `true` |
| `MAX_CONCURRENT_SSR_SEARCHES` | Concurrent SSR product searches | `3` |
| `MIN_SSR_DELAY_MS` | Minimum delay between SSR requests | `200` |
| `MAX_CONCURRENT_GRAPHQL` | Concurrent GraphQL calls | `5` |
| `MIN_GRAPHQL_DELAY_MS` | Minimum delay between GraphQL requests | `100` |
| `RETRY_ATTEMPTS` | Retries for failed requests | `3` |
| `CIRCUIT_BREAKER_THRESHOLD` | Failures before the breaker opens | `5` |
| `CIRCUIT_BREAKER_TIMEOUT` | Seconds before the breaker retries | `30` |
| `AUTH_STATE_PATH` | Session state file | `~/.texas-grocery-mcp/auth.json` |

See `utils/config.py` for the full list.

#### `TYPEAHEAD_FALLBACK_ENABLED`

When HEB's authenticated product search fails (expired session, WAF block,
frontend change), `product_search` can fall back to HEB's autocomplete
endpoint. Those results are **names only** - no real prices, no real product
IDs, so they can't be passed to `product_get`.

It's **off by default**, so a failed search returns zero products plus a
`fallback_reason` explaining why. Turn it on only if you'd rather have
suggestions than nothing, and check `data_source` in the response before
trusting any result.

---

## 🎯 Usage Examples

### 🏪 Finding a Store

```
User: Find HEB stores near Austin, TX

Agent uses: store_search(address="Austin, TX", radius_miles=10)
```

### 🔍 Searching Products

```
User: Search for organic milk

Agent uses: store_change(store_id="590")
Agent uses: product_search(query="organic milk")
```

### 📋 Getting Product Details

```
User: What are the ingredients in H-E-B olive oil?

Agent uses: product_search(query="heb olive oil")
Agent uses: product_get(product_id="127074")
# Returns: ingredients, nutrition facts, warnings, dietary attributes
```

The `product_get` tool returns:
- 🥗 **Ingredients** - Full ingredient statement
- 📊 **Nutrition Facts** - Complete FDA panel
- ⚠️ **Safety Warnings** - Allergen info and precautions
- 🌿 **Dietary Attributes** - Gluten-free, organic, vegan, kosher, etc.
- 📍 **Store Location** - Aisle or section

---

## 🔐 Session Management

HEB's bot detection (Imperva/Incapsula, via a `reese84` token) expires tokens
roughly every ~10-15 minutes
of active use, and it routinely blocks or rejects sessions that automated
browsers establish - so the reliable way to authenticate is importing cookies
from your own real, human-driven browser session.

### 🍪 Cookie Import (Recommended)

1. Log in to [heb.com](https://www.heb.com) in your normal browser and
   complete any verification prompts as usual.
2. Export cookies for `heb.com` with an extension like
   ["Get cookies.txt LOCALLY"](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc).
3. Paste the exported text into `session_load_cookies`:

```
Agent uses: session_load_cookies(cookies_txt="<pasted export>")
Agent uses: session_status()  # confirm it worked
```

Re-run this whenever your session stops working - expect to redo it every
so often rather than once-and-done, since HEB's bot-detection token rotates
frequently.

### ⚡ Auto-Refresh / Auto-Login (Experimental, unreliable)

`session_refresh()` and `session_save_credentials()` drive an embedded
Playwright browser to log in or refresh tokens automatically. In practice
this frequently gets blocked by HEB's bot detection, headless or not, and
even a full success there can still fail HEB's checks on later authenticated
calls. Treat these as a fallback to try, not the primary workflow - cookie
import above is what actually works.

---

## 🧰 Available Tools

### 🏪 Store Tools
| Tool | Description |
|------|-------------|
| `store_search` | Find stores by address or zip (`radius_miles` 1-100, default 25) |
| `store_change` | Set preferred store. Syncs to HEB.com when authenticated; otherwise sets a local default and says so via `method: "local_only"` |
| `store_get_default` | Get current default store |

### 🔍 Product Tools
| Tool | Description |
|------|-------------|
| `product_search` | Search products with pricing (`limit` 1-50, default 20; `fields`: `minimal`/`standard`/`all`) |
| `product_search_batch` | Search up to 20 queries at once (`limit_per_query` 1-20, default 5) |
| `product_get` | Get detailed product info by ID |

### 🔐 Session Tools
| Tool | Description |
|------|-------------|
| `session_status` | Check session health, token lifetime, and credential storage |
| `session_load_cookies` | Import cookies.txt from your browser (**recommended**) |
| `session_save_instructions` | Get the step-by-step manual authentication walkthrough |
| `session_refresh` | Refresh/login via embedded browser (best-effort; often blocked) |
| `session_save_credentials` | Save credentials for auto-login (same caveats) |
| `session_clear_credentials` | Remove saved credentials |
| `session_clear` | Clear saved session (logout) |

---

## 📚 Documentation

- 🔧 [Troubleshooting Guide](docs/TROUBLESHOOTING.md) - Solutions for common issues
- 🤝 [Contributing](CONTRIBUTING.md) - How to contribute
- 📝 [Changelog](CHANGELOG.md) - Version history
- 🔒 [Security](SECURITY.md) - Security policy

---

## 🛠️ Development

```bash
# Clone repository
git clone https://github.com/mgwalkerjr95/texas-grocery-mcp
cd texas-grocery-mcp

# Install with dev dependencies
pip install -e ".[dev]"
playwright install chromium

# Linting & type checking
ruff check src
mypy src

# Run the server directly
texas-grocery-mcp
```

There is currently no test suite - see [CONTRIBUTING.md](CONTRIBUTING.md#tests)
for why, and what would be welcome instead.

### 🐳 Docker

```bash
docker-compose up --build
```

---

## 🏗️ Architecture

```
        🍪 Your browser's cookies.txt export
                      │
                      ▼  session_load_cookies
┌─────────────────────────────────────────────────────────────┐
│              🛒 Texas Grocery MCP                           │
│                                                             │
│   tools/  ──▶  HEBGraphQLClient  ──▶  reliability/          │
│                      │                 (throttle, retry,    │
│                      │                  breaker, cache)     │
│                      │                                      │
│        ┌─────────────┴─────────────┐                        │
│        ▼                           ▼                        │
│  Persisted GraphQL           Next.js SSR scrape             │
│  (store search/select)       (product search + details)     │
│        │                           │                        │
│        └─────────────┬─────────────┘                        │
│                      │       ▼ on failure, if enabled       │
│                      │   Typeahead fallback (names only)    │
└──────────────────────┼──────────────────────────────────────┘
                       ▼
                 🌐 heb.com (unofficial endpoints, behind Imperva)
```

Store search uses HEB's persisted GraphQL queries. Product search scrapes
HEB's server-rendered pages instead, because that's where full pricing and
inventory actually appear. Both are reverse-engineered against HEB's current
frontend and **will break when HEB ships changes** - that's the expected
failure mode, not an anomaly.

---

## 📄 License

MIT © Michael Walker

---

<p align="center">
  Made with ❤️ in Texas 🤠
</p>
