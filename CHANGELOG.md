# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Removed
- **Cart tools** (`cart_check_auth`, `cart_get`, `cart_add`, `cart_add_many`,
  `cart_add_with_retry`, `cart_remove`) - HEB's bot detection made authenticated
  write operations unreliable enough that they were withdrawn rather than shipped broken
- **Coupon tools** (`coupon_list`, `coupon_search`, `coupon_categories`,
  `coupon_clip`, `coupon_clipped`) - same reason
- **Health tools** (`health_live`, `health_ready`) and the `observability/health.py`
  module backing them
- Unit test suite - the mocked HTTP fixtures no longer reflected HEB's live
  behavior, which is what this project actually has to survive

### Added
- `session_load_cookies` - import a Netscape `cookies.txt` export from your own
  browser session. This is now the **recommended** way to authenticate; see README
- `session_save_instructions` - returns the manual authentication walkthrough
- `TYPEAHEAD_FALLBACK_ENABLED` setting (default `false`) - controls whether
  `product_search` falls back to HEB's autocomplete API when SSR search fails.
  When off, a failed search returns zero products plus a `fallback_reason`
  instead of placeholder suggestions with no real prices or product IDs

### Changed
- Store search and typeahead now track HEB's updated GraphQL persisted-query hashes
- Improved geocoding address handling for bare zip codes and partial addresses
- Browser fingerprint (user agent + Client Hints) is now derived from the launched
  browser binary rather than hardcoded, so it stops contradicting itself
- Documentation now leads with cookie import; `session_refresh` and
  `session_save_credentials` are documented as best-effort fallbacks

## [0.1.2] - 2026-02-02

### Changed
- README redesign with emojis and improved formatting
- Feature tables for better readability
- Tools organized in clean tables

### Fixed
- Placeholder link in TROUBLESHOOTING.md

### Removed
- firebase-debug.log from repository

## [0.1.1] - 2026-02-02

### Added
- Project URLs in PyPI metadata (homepage, repository, issues, changelog)
- PyPI, license, and CI badges in README
- CONTRIBUTING.md, SECURITY.md documentation

### Fixed
- GitHub repository URL in README

## [0.1.0] - 2026-02-02

### Added

- Initial public release
- **Store Tools**
  - `store_search` - Find HEB stores by address or zip code
  - `store_change` - Set preferred store (syncs with HEB.com when authenticated)
  - `store_get_default` - Get current default store
- **Product Tools**
  - `product_search` - Search products by name with pricing and availability
  - `product_search_batch` - Search multiple products at once (up to 20 queries)
  - `product_get` - Get comprehensive product details (ingredients, nutrition, warnings, dietary attributes)
- **Cart Tools**
  - `cart_check_auth` - Check authentication status
  - `cart_get` - View cart contents
  - `cart_add` - Add item with human-in-the-loop confirmation
  - `cart_add_many` - Bulk add multiple items
  - `cart_add_with_retry` - Add item with automatic retry on failure
  - `cart_remove` - Remove item with confirmation
- **Coupon Tools**
  - `coupon_list` - List available digital coupons
  - `coupon_search` - Search coupons by keyword
  - `coupon_categories` - Get coupon category list
  - `coupon_clip` - Clip a coupon to your account
  - `coupon_clipped` - List your clipped coupons
- **Session Tools**
  - `session_status` - Check session health and token expiration
  - `session_refresh` - Refresh/login with embedded browser or Playwright MCP
  - `session_save_credentials` - Save credentials for auto-login (secure keyring storage)
  - `session_clear_credentials` - Remove saved credentials
  - `session_clear` - Clear saved session (logout)
- **Health Tools**
  - `health_live` - Liveness probe
  - `health_ready` - Readiness probe with component status
- Fast session refresh with embedded Playwright (~15 seconds)
- Human-in-the-loop confirmation for cart and coupon operations
- Request throttling to prevent rate limiting
- In-memory and Redis caching support
- Docker support with docker-compose
- CI/CD with GitHub Actions

[0.1.1]: https://github.com/mgwalkerjr95/texas-grocery-mcp/releases/tag/v0.1.1
[0.1.0]: https://github.com/mgwalkerjr95/texas-grocery-mcp/releases/tag/v0.1.0
