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
| 🔄 **Auto Session Refresh** | Handles bot detection automatically (~15 seconds) |

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

### Prerequisites

For store changes and session management, you'll also need **Playwright MCP**:

```bash
npm install -g @anthropic-ai/mcp-playwright
```

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
| `REDIS_URL` | Redis cache URL | None (in-memory) |
| `LOG_LEVEL` | Logging level | INFO |

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

HEB uses bot detection that expires every ~11 minutes. This MCP handles it automatically!

### ⚡ Fast Auto-Refresh (Recommended)

With `[browser]` support installed:

```
Agent uses: session_refresh()
# ✅ Completes in ~10-15 seconds
```

### 🔑 Auto-Login

Save your credentials once for automatic login:

```
Agent uses: session_save_credentials(email="you@email.com", password="...")
# Credentials stored securely in system keyring
# Future session refreshes will auto-login!
```

---

## 🧰 Available Tools

### 🏪 Store Tools
| Tool | Description |
|------|-------------|
| `store_search` | Find stores by address |
| `store_change` | Set preferred store |
| `store_get_default` | Get current default store |

### 🔍 Product Tools
| Tool | Description |
|------|-------------|
| `product_search` | Search products with pricing |
| `product_search_batch` | Search multiple products (up to 20) |
| `product_get` | Get detailed product info |

### 🔐 Session Tools
| Tool | Description |
|------|-------------|
| `session_status` | Check session health |
| `session_refresh` | Refresh/login session |
| `session_save_credentials` | Save credentials for auto-login |
| `session_clear` | Logout |

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

# Run tests
pytest tests/ -v

# Linting & type checking
ruff check src/
mypy src/
```

### 🐳 Docker

```bash
docker-compose up --build
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User's MCP Environment                    │
│                                                             │
│  ┌─────────────────────┐    ┌─────────────────────────────┐ │
│  │  🎭 Playwright MCP  │    │   🛒 Texas Grocery MCP      │ │
│  │  (Browser Auth)     │───▶│   (Grocery Logic)           │ │
│  └─────────────────────┘    └─────────────────────────────┘ │
│                                        │                     │
└────────────────────────────────────────┼─────────────────────┘
                                         │
                                         ▼
                                   🌐 HEB GraphQL API
```

---

## 📄 License

MIT © Michael Walker

---

<p align="center">
  Made with ❤️ in Texas 🤠
</p>
