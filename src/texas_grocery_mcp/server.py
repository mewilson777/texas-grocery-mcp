"""Texas Grocery MCP Server - FastMCP entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version

import structlog
from fastmcp import FastMCP

from texas_grocery_mcp.observability.logging import configure_logging
from texas_grocery_mcp.tools.product import product_get, product_search, product_search_batch
from texas_grocery_mcp.tools.session import (
    session_clear,
    session_clear_credentials,
    session_load_cookies,
    session_refresh,
    session_save_credentials,
    session_save_instructions,
    session_status,
)
from texas_grocery_mcp.tools.store import (
    store_change,
    store_get_default,
    store_search,
)
from texas_grocery_mcp.utils.config import get_settings

# Configure logging before anything else
configure_logging()

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastMCP) -> AsyncIterator[None]:
    """Lifespan hook for startup/shutdown tasks.

    On startup:
    - Checks session status
    - Auto-refreshes if enabled and session needs refresh
    """
    settings = get_settings()

    # Startup: Check and refresh session if needed
    if settings.auto_refresh_on_startup:
        try:
            from texas_grocery_mcp.auth.session import get_session_status

            status = get_session_status()
            logger.info(
                "Startup session check",
                authenticated=status["authenticated"],
                needs_refresh=status["needs_refresh"],
                time_remaining_hours=status["time_remaining_hours"],
            )

            # Auto-refresh if needed
            if status["needs_refresh"] or (
                status["time_remaining_hours"] is not None
                and status["time_remaining_hours"] < settings.auto_refresh_threshold_hours
            ):
                logger.info("Startup auto-refresh triggered")
                try:
                    result = await session_refresh(headless=True)
                    if result.get("success"):
                        logger.info(
                            "Startup session refresh successful",
                            elapsed_seconds=result.get("elapsed_seconds"),
                        )
                    else:
                        logger.warning(
                            "Startup session refresh failed",
                            error=result.get("error"),
                            error_type=result.get("error_type"),
                        )
                except Exception as e:
                    logger.warning("Startup session refresh error", error=str(e))

        except Exception as e:
            logger.warning("Startup session check failed", error=str(e))

    yield  # Server runs here

    # Shutdown: close the shared authenticated browser. Authenticated requests
    # run inside a live Chrome that's kept open for the process lifetime, so
    # without this it outlives the server.
    logger.info("MCP server shutting down")
    try:
        from texas_grocery_mcp.auth.browser_session import get_browser_session

        await get_browser_session().close()
    except Exception as e:
        logger.warning("Error closing browser session on shutdown", error=str(e))

MCP_INSTRUCTIONS = """
## Texas Grocery MCP - Session Management

This MCP requires an authenticated HEB.com session for most operations.

### Recommended: manual cookie import (`session_load_cookies`)
HEB's bot detection (Imperva/Incapsula) routinely blocks or rejects sessions
established by automated browsers, including this MCP's own `session_refresh`
tool - treat `session_refresh` as a best-effort fallback, not the primary
path. The workflow that actually works:

1. Ask the user to log in to https://www.heb.com in their own regular
   browser and complete any verification prompts normally.
2. Ask them to export cookies for `heb.com` with a browser extension such as
   "Get cookies.txt LOCALLY".
3. Call `session_load_cookies(cookies_txt=...)` with that exported text
   pasted directly in (not a file path).
4. Call `session_status` to confirm authentication succeeded.

Re-run this whenever the session stops working - HEB rotates its bot-detection
token roughly every ~10 minutes of active use, so expect to redo this
periodically rather than expecting one export to last.

Note: even a freshly-loaded, valid cookie set may still get rejected on
write operations like `store_change` - HEB's WAF can distrust API calls that
don't originate from the live browser session that established them. If
`store_change` fails with 401 right after a successful `session_load_cookies`,
that's this limitation, not a bad cookie export.

### Session states:
- `authenticated: true, needs_refresh: false` → Ready to use all tools
- `authenticated: true, refresh_recommended: true` → Works but consider refreshing soon
- `authenticated: false` or `needs_refresh: true` → Needs `session_load_cookies` before store_change

### Tools that work WITHOUT authentication:
- `store_search` - Find stores by address
- `session_status` - Check session state

### Tools that work unauthenticated but return better data with a session:
- `product_search` / `product_search_batch` - Search products (uses local store default)
- `product_get` - Get detailed product info (ingredients, nutrition, warnings)

Without a session these return limited or empty results: full pricing and
inventory come from HEB's authenticated pages. Check `data_source` and
`authenticated` in the response - `data_source: "none"` means the search
failed and typeahead fallback is disabled (the default).

Important caveat: these product tools auto-refresh the session first, so if a
*stale* session file exists, they can return `LOGIN_REQUIRED` or
`HUMAN_ACTION_REQUIRED` instead of results rather than silently proceeding
unauthenticated. If that happens, run `session_load_cookies` and retry. (With
no session file at all, they proceed unauthenticated as described above.)

### Tools that REQUIRE authentication:
- `store_change` - Change store on HEB.com account

### Typical workflow:
1. `session_status` → Check if authenticated
2. If not authenticated: walk the user through `session_load_cookies` (see above)
3. `store_search("address")` → Find nearby stores
4. `store_change(store_id)` → Set preferred store
5. `product_search("query")` → Search for products

### `session_refresh` (best-effort fallback only)
Uses an embedded Playwright browser to log in or refresh tokens
automatically. In practice this frequently fails against HEB's bot
detection regardless of headless/visible mode - don't rely on it as the
primary way to authenticate. If you do try it and it needs human input, it
returns:
- `status: "human_action_required"` - Clear indicator that human action is needed
- `action: "login" | "captcha" | "2fa" | "waf"` - What type of action is needed
- `screenshot_path: "/tmp/heb-login-<action>-123456.png"` - Screenshot of what's shown

If it hands off, read the screenshot, tell the user what's needed, and call
`session_refresh()` again after they act - but if it doesn't get past HEB's
detection, fall back to `session_load_cookies` instead of retrying it repeatedly.

### Automatic Login (Optional, same reliability caveats as session_refresh)
`session_save_credentials(email, password)` stores credentials for
`session_refresh` to auto-login with. Subject to the same bot-detection
limitations described above.
"""

try:
    __version__ = version("texas-grocery-mcp")
except PackageNotFoundError:  # pragma: no cover - source checkout without install
    __version__ = "0.0.0+unknown"

mcp = FastMCP(
    name="texas-grocery-mcp",
    version=__version__,
    instructions=MCP_INSTRUCTIONS,
    lifespan=lifespan,
)

# Register store tools
mcp.tool(annotations={"readOnlyHint": True})(store_search)
mcp.tool(annotations={"readOnlyHint": True})(store_get_default)
mcp.tool()(store_change)  # Changes store on HEB.com when authenticated, or sets local default

# Register product tools
mcp.tool(annotations={"readOnlyHint": True})(product_search)
mcp.tool(annotations={"readOnlyHint": True})(product_search_batch)
mcp.tool(annotations={"readOnlyHint": True})(product_get)

# Register session tools
mcp.tool(annotations={"readOnlyHint": True})(session_status)
mcp.tool(annotations={"readOnlyHint": True})(session_save_instructions)
mcp.tool()(session_refresh)  # Uses embedded Playwright when available, falls back to commands
mcp.tool()(session_load_cookies)  # Load cookies from Netscape cookies.txt export
mcp.tool()(session_clear)
mcp.tool()(session_save_credentials)  # Store HEB credentials for auto-login
mcp.tool()(session_clear_credentials)  # Remove stored credentials


def main() -> None:
    """Run the MCP server."""
    mcp.run(
        transport="streamable-http",
        host="127.0.0.1",
        port=3000,
    )


if __name__ == "__main__":
    main()
