"""Shared browser fingerprint for Playwright launches and httpx requests.

HEB's WAF (Imperva) cross-checks the UA string against the Client Hints
headers (``sec-ch-ua``, ``sec-ch-ua-platform``) and the browser binary's own
behaviour. Two non-obvious traps this module exists to avoid:

1. Playwright's ``user_agent=`` context option rewrites ONLY the UA string;
   ``sec-ch-ua`` still comes from the actual binary. Overriding the UA to
   claim a different brand/version/OS than the binary therefore *creates* a
   mismatch rather than hiding one. Measured against a HAR of a real Chrome
   153 session, the previous hardcoded "Chrome/120 macOS" override sent
   ``sec-ch-ua: "HeadlessChrome";v="147"`` with ``sec-ch-ua-platform: "macOS"``
   from a Linux box - three contradictions at once.
2. Headless Chrome brands itself ``HeadlessChrome/<major>`` in the UA string.
   The only UA override we apply is derived from the launched browser's own
   reported version, so it stays truthful about brand/version/OS while
   dropping that one headless marker.

So: prefer the real ``chrome`` channel (matching Client Hints for free), and
never claim a brand the running binary isn't.
"""

import sys
from typing import Any

import structlog

logger = structlog.get_logger()

# Real Chrome, not Playwright's bundled Chromium. Bundled Chromium lacks
# proprietary codecs/widevine and brands its Client Hints as "Chromium"/
# "HeadlessChrome", which no real browser sends.
CHROME_CHANNEL = "chrome"

LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-infobars",
]

# Chrome sends q=0.9 here; the previous value (q=0.5) is Firefox's format.
# Must be set via extra_http_headers with NO locale= alongside it: Playwright's
# locale= wins over extra_http_headers for this header and yields a bare
# "en-US", and it also narrows navigator.languages to ["en-US"] where real
# Chrome reports ["en-US", "en"]. Omitting locale= gets both right.
ACCEPT_LANGUAGE = "en-US,en;q=0.9"

# Used by httpx, which has no launched browser to derive a version from.
FALLBACK_CHROME_MAJOR = 153


def _platform_token() -> str:
    """UA platform token for the host OS.

    Claiming a different OS than the machine actually runs is detectable via
    TLS/h2 fingerprint, so this follows the real platform.
    """
    if sys.platform == "darwin":
        return "Macintosh; Intel Mac OS X 10_15_7"
    if sys.platform == "win32":
        return "Windows NT 10.0; Win64; x64"
    return "X11; Linux x86_64"


def chrome_user_agent(major: int) -> str:
    """Build a Chrome UA string. Chrome's UA reduction fixes the minor
    components at ``0.0.0``, so only the major version varies.
    """
    return (
        f"Mozilla/5.0 ({_platform_token()}) AppleWebKit/537.36 "
        f"(KHTML, like Gecko) Chrome/{major}.0.0.0 Safari/537.36"
    )


DEFAULT_USER_AGENT = chrome_user_agent(FALLBACK_CHROME_MAJOR)


async def launch_browser(playwright: Any, *, headless: bool) -> Any:
    """Launch real Chrome, falling back to bundled Chromium if unavailable.

    Args:
        playwright: Started Playwright instance.
        headless: Whether to run without a visible window.

    Returns:
        The launched Browser.
    """
    try:
        browser = await playwright.chromium.launch(
            channel=CHROME_CHANNEL,
            headless=headless,
            args=LAUNCH_ARGS,
        )
        logger.info("Launched real Chrome", version=browser.version, headless=headless)
        return browser
    except Exception as e:
        logger.warning(
            "Real Chrome unavailable, falling back to bundled Chromium - its "
            "Client Hints brand themselves as Chromium/HeadlessChrome and are "
            "more likely to be challenged. Install Chrome to avoid this.",
            error=str(e),
        )
        browser = await playwright.chromium.launch(headless=headless, args=LAUNCH_ARGS)
        logger.info("Launched bundled Chromium", version=browser.version, headless=headless)
        return browser


def context_kwargs(browser: Any, **extra: Any) -> dict[str, Any]:
    """Context options whose UA matches ``browser``'s real brand and version.

    Args:
        browser: An already-launched Browser (its reported version drives the UA).
        **extra: Passed through (e.g. ``storage_state``).

    Returns:
        kwargs for ``browser.new_context()``.
    """
    major = FALLBACK_CHROME_MAJOR
    try:
        major = int(str(browser.version).split(".", 1)[0])
    except (ValueError, AttributeError, IndexError):
        logger.warning(
            "Could not parse browser version, using fallback UA",
            version=getattr(browser, "version", None),
        )

    return {
        "user_agent": chrome_user_agent(major),
        "extra_http_headers": {"Accept-Language": ACCEPT_LANGUAGE},
        **extra,
    }
