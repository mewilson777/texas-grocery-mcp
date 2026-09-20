"""Persistent authenticated Playwright browser session.

``httpx`` cannot replicate a real browser's TLS handshake or
``sec-fetch-*``/client-hint headers, and HEB's WAF gates account-scoped
endpoints (the SSR ``/search`` page, GraphQL mutations like
``SelectPickupFulfillment``) on exactly those signals - a verified-fresh
cookie jar sent over ``httpx`` still gets 401'd. Two more targeted fixes
were tried and both still 401'd: swapping in a real Playwright browser
loaded from ``storage_state``, and adding the same reese84 warm-up wait
``session_refresh`` uses. What actually succeeded every time, across many
attempts, was the live browser *inside* ``refresh_session_with_browser``
itself, checked immediately, without ever closing it.

The common thread: every failing attempt replayed saved cookies/localStorage
into a *new* browser process; the one success never closed the browser that
logged in at all. HEB's bot detection (Incapsula) appears to bind trust to
the live session/connection that generated the token, not just the token
values - so serialize-and-replay elsewhere doesn't work no matter how
faithfully the replaying client behaves.

UPDATE 2026-09-20: the conclusion above was reached while every Playwright
launch was sending a self-contradicting fingerprint - bundled Chromium 147
branding its Client Hints as ``"HeadlessChrome";v="147"`` underneath a UA
string claiming Chrome 120 on macOS (see ``browser_fingerprint``). With that
corrected, replaying ``storage_state`` into a *fresh* headless browser was
observed fetching the authenticated search endpoint successfully (HTTP 200,
full results), so device-identity binding was probably never the whole story
- the replaying browser was simply identifiable as automation. Treat the
"only a live browser works" rule as a strong default rather than a law.

Either way, keeping ONE page alive is still preferable: it avoids a fresh
launch plus reese84 warm-up on every call.
``refresh_session_with_browser`` hands its already-authenticated, still-open
browser over via :meth:`AuthenticatedBrowserSession.adopt` instead of
closing it, so the same live session that logged in goes on to directly
serve ``search_products``/``select_store`` calls. Loading from
``storage_state`` remains the fallback for bootstrapping before any
``session_refresh`` has run in this process.

All calls go through the one shared page, serialized by a lock - Playwright
pages aren't safe for concurrent navigation.
"""

import json
from contextlib import suppress
from pathlib import Path
from typing import Any

import structlog

from texas_grocery_mcp.auth.browser_fingerprint import context_kwargs, launch_browser
from texas_grocery_mcp.utils.config import get_settings

logger = structlog.get_logger()

# Incapsula's own device/session-identity cookies, not HEB login cookies.
# Loading auth.json wholesale into a new browser presents this same device
# identity on every launch; if Incapsula ever flags it, every subsequent
# launch inherits the flag instead of starting clean. Stripped out whenever
# storage_state is loaded from disk so each new browser gets fresh ones.
_INCAPSULA_DEVICE_COOKIE_PREFIXES = ("incap_ses_", "visid_incap_")


def load_storage_state_without_device_id(auth_path: Path) -> dict[str, Any] | None:
    """Load a Playwright storage-state dict from ``auth_path``, stripping
    Incapsula's device-identity cookies (see module-level comment).

    Args:
        auth_path: Path to auth.json

    Returns:
        The storage-state dict with those cookies removed, or None if the
        file doesn't exist or can't be read/parsed.
    """
    if not auth_path.exists():
        return None
    try:
        state: dict[str, Any] = json.loads(auth_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to read auth.json for storage_state", error=str(e))
        return None

    original_cookies = state.get("cookies", [])
    filtered_cookies = [
        c
        for c in original_cookies
        if not str(c.get("name", "")).startswith(_INCAPSULA_DEVICE_COOKIE_PREFIXES)
    ]
    if len(filtered_cookies) != len(original_cookies):
        logger.info(
            "Stripped Incapsula device-identity cookies from storage_state",
            removed=len(original_cookies) - len(filtered_cookies),
        )
    state["cookies"] = filtered_cookies
    return state

def strip_reese84(state: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``state`` with the saved reese84 token removed.

    HEB's bot-detection script only mints a new reese84 token when the page
    doesn't already have a usable one. A browser started from a storage state
    that still carries the old token therefore *reuses* it - so a "refresh"
    writes the same token, with the same expiry, back to disk and the session
    never actually gains any life.

    Measured 2026-09-22, loading the same auth.json into a fresh browser:
      - token carried over -> same token, renewInSec counting down 210 -> 106
      - token stripped     -> brand new token, renewInSec 896

    So refreshes drop it and let the page issue a fresh one.

    Args:
        state: Playwright storage state dict

    Returns:
        A shallow copy with reese84 removed from cookies and from every
        origin's localStorage.
    """
    stripped = dict(state)
    stripped["cookies"] = [
        c for c in state.get("cookies", []) if c.get("name") != "reese84"
    ]
    stripped["origins"] = [
        {
            **origin,
            "localStorage": [
                item
                for item in origin.get("localStorage", [])
                if item.get("name") != "reese84"
            ],
        }
        for origin in state.get("origins", [])
    ]
    return stripped


def load_storage_state_for_refresh(auth_path: Path) -> dict[str, Any] | None:
    """Load auth.json for a session *refresh*: no device identity, no reese84.

    Keeps the login cookies (``sat``/``sst``/``JSESSIONID``) so the refreshed
    browser is still signed in, while dropping both the Incapsula device
    cookies and the stale bot-detection token so the page issues a new one.

    Args:
        auth_path: Path to auth.json

    Returns:
        The storage-state dict, or None if there's nothing loadable on disk.
    """
    state = load_storage_state_without_device_id(auth_path)
    if state is None:
        return None
    return strip_reese84(state)


try:
    from playwright.async_api import async_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    async_playwright = None  # type: ignore[assignment]

# How long to let HEB's reese84 script finish after landing on the homepage,
# before trusting the session enough to use it - mirrors browser_refresh.py's
# "Waiting for reese84 token generation..." step. Only used by the
# storage_state fallback bootstrap; adopt() skips this since
# refresh_session_with_browser already did it.
_WARMUP_WAIT_MS = 5000


class BrowserSessionUnavailableError(Exception):
    """Raised when the persistent browser session can't be used.

    Covers: Playwright not installed, or no live/authenticated session to
    use or bootstrap from.
    """


class AuthenticatedBrowserSession:
    """The one authenticated headless page shared by refresh and by requests.

    Never recycled on a timer - once a live, working page exists (via
    ``adopt`` from a successful refresh, or the ``storage_state`` fallback
    bootstrap), it's kept and reused indefinitely. It's only replaced when
    ``adopt`` hands over a fresh one (a new successful refresh) or ``close``
    is called explicitly.
    """

    def __init__(self) -> None:
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._page: Any = None
        self._lock: Any = None  # created lazily to bind to the running event loop

    def _get_lock(self) -> Any:
        if self._lock is None:
            import asyncio

            self._lock = asyncio.Lock()
        return self._lock

    async def adopt(self, playwright: Any, browser: Any, context: Any, page: Any) -> None:
        """Adopt an already-authenticated, live browser as the shared session.

        Replaces (and closes) whatever this session currently holds. Used
        right after a successful headless ``session_refresh`` so the browser
        that just logged in keeps serving authenticated requests directly,
        instead of being closed - per this module's docstring, closing and
        later replaying its saved cookies into a separate browser has not
        worked in practice.

        Args:
            playwright: The started Playwright driver (caller must NOT stop it)
            browser: The live, authenticated Browser (caller must NOT close it)
            context: The BrowserContext holding the authenticated cookies
            page: A Page on that context, already warmed up
        """
        async with self._get_lock():
            await self._close_locked()
            self._playwright = playwright
            self._browser = browser
            self._context = context
            self._page = page
            logger.info("Adopted live authenticated browser session")

    async def _ensure_page(self) -> Any:
        """Get the shared page, bootstrapping from auth.json if none exists yet.

        Caller must hold self._get_lock().
        """
        if not PLAYWRIGHT_AVAILABLE:
            raise BrowserSessionUnavailableError(
                "Playwright not installed. Install with: "
                "pip install texas-grocery-mcp[browser] && playwright install chromium"
            )

        if self._page is not None:
            return self._page

        # Fallback bootstrap: no session has been adopted yet in this process
        # (no session_refresh has run since startup). Runs headless - see the
        # module docstring on why replaying storage_state is now viable.
        settings = get_settings()
        auth_path = Path(settings.auth_state_path).expanduser()
        if not auth_path.exists():
            raise BrowserSessionUnavailableError(
                "No authenticated browser session available. Run session_refresh first."
            )

        logger.info(
            "Bootstrapping browser session from saved auth.json "
            "(no session_refresh has run in this process)"
        )

        self._playwright = await async_playwright().start()
        self._browser = await launch_browser(self._playwright, headless=True)
        self._context = await self._browser.new_context(
            **context_kwargs(
                self._browser,
                storage_state=load_storage_state_without_device_id(auth_path),
            )
        )
        self._page = await self._context.new_page()

        logger.info("Warming up authenticated browser page...")
        await self._page.goto("https://www.heb.com", wait_until="load", timeout=30000)
        await self._page.wait_for_timeout(_WARMUP_WAIT_MS)

        logger.info("Authenticated browser page ready")
        return self._page

    async def _close_locked(self) -> None:
        """Close browser/playwright. Caller must hold self._get_lock()."""
        if self._browser is not None:
            with suppress(Exception):
                await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            with suppress(Exception):
                await self._playwright.stop()
            self._playwright = None
        self._context = None
        self._page = None

    async def close(self) -> None:
        """Close the browser session. Safe to call even if never opened."""
        async with self._get_lock():
            await self._close_locked()

    async def fetch_html(self, url: str, timeout_ms: int = 30000) -> tuple[str, int]:
        """Navigate the shared page to ``url`` and return (html, status).

        Args:
            url: URL to load
            timeout_ms: Navigation timeout

        Returns:
            (page_html, http_status). status is 0 if no response was received.
        """
        async with self._get_lock():
            page = await self._ensure_page()
            response = await page.goto(url, wait_until="load", timeout=timeout_ms)
            status = response.status if response else 0
            html = await page.content()
            return html, status

    async def fetch_json(
        self,
        url: str,
        payload: dict[str, Any],
        timeout_ms: int = 30000,
    ) -> tuple[dict[str, Any], int]:
        """POST JSON to ``url`` via the shared page's own ``fetch()``.

        Runs the request from inside the already-authenticated page (already
        on a heb.com origin), so it carries the same TLS/session fingerprint
        as a real navigation.

        Args:
            url: URL to POST to
            payload: JSON body
            timeout_ms: Timeout for the fetch() call itself

        Returns:
            (response_json, http_status). response_json is {} if the body
            wasn't valid JSON.
        """
        async with self._get_lock():
            page = await self._ensure_page()
            result = await page.evaluate(
                """async ({url, payload}) => {
                    const res = await fetch(url, {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        credentials: 'include',
                        body: JSON.stringify(payload),
                    });
                    const text = await res.text();
                    let json = null;
                    try { json = JSON.parse(text); } catch (e) { /* non-JSON body */ }
                    return { status: res.status, json };
                }""",
                {"url": url, "payload": payload},
            )
            return (result.get("json") or {}), result.get("status", 0)

    async def get_json(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        timeout_ms: int = 30000,
    ) -> tuple[Any, int, str]:
        """GET ``url`` via the shared page's own ``fetch()``.

        Same rationale as :meth:`fetch_json`, for GET endpoints like
        ``/_next/data/{build_id}/en/search.json``. httpx is blocked on these
        by Imperva regardless of cookies (verified 2026-09-20); the same URL
        from inside the page returns 200.

        Args:
            url: URL to GET
            headers: Extra request headers
            timeout_ms: Unused; kept for signature symmetry with fetch_html

        Returns:
            (parsed_json_or_None, http_status, body_text). ``body_text`` is
            only populated when the body wasn't valid JSON, so callers can
            check it for a WAF challenge page without copying large JSON
            payloads across the CDP bridge twice.
        """
        async with self._get_lock():
            page = await self._ensure_page()
            result = await page.evaluate(
                """async ({url, headers}) => {
                    const res = await fetch(url, {
                        headers: headers || {},
                        credentials: 'include',
                    });
                    const text = await res.text();
                    try {
                        return { status: res.status, json: JSON.parse(text), text: '' };
                    } catch (e) {
                        return { status: res.status, json: null, text: text.slice(0, 2000) };
                    }
                }""",
                {"url": url, "headers": headers or {}},
            )
            return result.get("json"), result.get("status", 0), result.get("text", "")

    async def get_build_id(self) -> str | None:
        """Read the Next.js build ID out of the live page.

        Avoids httpx's homepage GET, which Imperva challenges.

        Returns:
            The build ID, or None if it couldn't be found on the page.
        """
        async with self._get_lock():
            page = await self._ensure_page()
            build_id: str | None = await page.evaluate(
                r"""() => {
                    const el = document.getElementById('__NEXT_DATA__');
                    if (el) {
                        try { return JSON.parse(el.textContent).buildId; } catch (e) {}
                    }
                    const m = document.documentElement.innerHTML.match(
                        /\/_next\/static\/([A-Za-z0-9_-]+)\/_buildManifest\.js/
                    );
                    return m ? m[1] : null;
                }"""
            )
            return build_id

    def has_live_session(self) -> bool:
        """Whether a live page already exists (no bootstrap attempted)."""
        return self._page is not None


_session: AuthenticatedBrowserSession | None = None


def get_browser_session() -> AuthenticatedBrowserSession:
    """Get the process-wide persistent authenticated browser session."""
    global _session
    if _session is None:
        _session = AuthenticatedBrowserSession()
    return _session
