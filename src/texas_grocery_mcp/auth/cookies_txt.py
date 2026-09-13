"""Load HEB session cookies from a Netscape ``cookies.txt`` file.

This is the recommended way to hand HEB cookies to the MCP: export them from
a real, human-driven browser (via a "Get cookies.txt" extension or similar)
so HEB's Kasada / reese84 bot detection has nothing automated to fingerprint.

The rest of the codebase reads ``auth.json`` in Playwright storage-state
format (``{"cookies": [...], "origins": [{"origin": ..., "localStorage": [...]}]}``),
so we translate Netscape rows into that shape and merge any pre-existing
localStorage entries (e.g. a previously captured reese84 token) instead of
dropping them.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypedDict

import structlog

logger = structlog.get_logger()


# Netscape rows are tab-separated with these columns, in order.
_NETSCAPE_COLUMNS = 7
_HTTPONLY_PREFIX = "#HttpOnly_"

# Only these HEB domains are trusted; anything else (e.g. a tracker or
# unrelated site swept up in a browser-wide export) is dropped.
_ALLOWED_DOMAINS = {".heb.com", "www.heb.com"}


class CookiesTxtParseError(ValueError):
    """Raised when a ``cookies.txt`` file cannot be parsed."""


class ParsedCookies(TypedDict):
    """Result of parsing a cookies.txt file."""

    cookies: list[dict[str, Any]]  # Playwright-format cookie dicts
    skipped: int  # rows that couldn't be parsed (blank / malformed)
    total: int  # rows the parser looked at


def parse_netscape_cookies(text: str) -> ParsedCookies:
    """Parse Netscape ``cookies.txt`` text into Playwright-format cookies.

    The Netscape format (as emitted by curl / most browser extensions) is::

        # optional comment lines
        <domain>\\t<include_subdomains>\\t<path>\\t<secure>\\t<expires>\\t<name>\\t<value>

    A domain prefixed with ``#HttpOnly_`` marks the cookie HttpOnly. Regular
    lines starting with ``#`` are comments and ignored.

    Args:
        text: Full contents of a ``cookies.txt`` file.

    Returns:
        ParsedCookies with Playwright-shape cookie dicts. Rows that don't
        parse are counted in ``skipped`` rather than raising, so a single
        malformed line doesn't discard a whole export.

    Raises:
        CookiesTxtParseError: If no valid cookie rows were found at all.
    """
    cookies: list[dict[str, Any]] = []
    skipped = 0
    total = 0

    for raw_line in text.splitlines():
        line = raw_line.rstrip("\r\n")
        if not line.strip():
            continue

        # Comments — except for the HttpOnly marker, which is part of the row.
        http_only = False
        if line.startswith("#"):
            if line.startswith(_HTTPONLY_PREFIX):
                http_only = True
                line = line[len(_HTTPONLY_PREFIX):]
            else:
                continue

        total += 1
        fields = line.split("\t")
        if len(fields) != _NETSCAPE_COLUMNS:
            skipped += 1
            logger.debug("Skipping malformed cookies.txt row", field_count=len(fields))
            continue

        domain, include_sub, path, secure, expires_str, name, value = fields

        # Netscape expires=0 means "session cookie"; Playwright uses -1 for that.
        # Some exporters emit a decimal (e.g. "1234567890.123456"), so parse as
        # a float rather than assuming an int.
        try:
            expires_float = float(expires_str)
        except ValueError:
            skipped += 1
            logger.debug("Skipping cookies.txt row with bad expires", expires=expires_str)
            continue
        expires: float = -1 if expires_float == 0 else expires_float

        if domain not in _ALLOWED_DOMAINS:
            skipped += 1
            logger.info("Skipping cookies.txt row with unused domain", domain=domain)
            continue

        cookies.append(
            {
                "name": name,
                "value": value,
                "domain": domain,
                "path": path or "/",
                "expires": expires,
                "httpOnly": http_only,
                "secure": secure.upper() == "TRUE",
                "sameSite": "Lax",  # Netscape format doesn't carry SameSite; Lax is safe default
                # include_subdomains is implicit in Playwright cookies (leading dot on domain),
                # so we don't emit it as its own field.
                "_includeSubdomains": include_sub.upper() == "TRUE",
            }
        )

    if not cookies:
        raise CookiesTxtParseError(
            "No cookies parsed from file. Expected Netscape cookies.txt format "
            "(tab-separated: domain, include_subdomains, path, secure, expires, name, value)."
        )

    # _includeSubdomains was only a debugging aid; strip it before returning.
    for cookie in cookies:
        cookie.pop("_includeSubdomains", None)

    return ParsedCookies(cookies=cookies, skipped=skipped, total=total)


def merge_into_storage_state(
    cookies: list[dict[str, Any]],
    existing: dict[str, Any] | None,
) -> dict[str, Any]:
    """Merge parsed cookies into a Playwright-format storage state.

    Keeps any existing localStorage (so a previously captured reese84 token
    stays put) and any non-HEB cookies untouched. HEB cookies are fully
    replaced by ``cookies`` (which ``parse_netscape_cookies`` has already
    restricted to ``_ALLOWED_DOMAINS``).

    Args:
        cookies: Playwright-format cookies to write in.
        existing: Existing storage state dict, or None for a fresh file.

    Returns:
        New storage state dict ready to serialize with ``json.dumps``.
    """
    state: dict[str, Any] = {"cookies": [], "origins": []}
    if existing:
        state["cookies"] = list(existing.get("cookies", []))
        state["origins"] = list(existing.get("origins", []))

    # Drop pre-existing HEB cookies; keep everything else.
    state["cookies"] = [
        c for c in state["cookies"] if c.get("domain") not in _ALLOWED_DOMAINS
    ]
    state["cookies"].extend(cookies)

    return state


def load_cookies_text(
    cookies_text: str,
    auth_path: Path,
) -> dict[str, Any]:
    """Parse raw Netscape ``cookies.txt`` text and write ``auth.json`` in Playwright format.

    This is the single entry point wired up as the ``session_load_cookies``
    MCP tool. Unlike ``load_cookies_txt``, it takes the cookie file's
    *contents* directly rather than a filesystem path — Claude can paste in
    text the user pasted into chat or read from anywhere, without needing
    filesystem access to wherever the export landed. It:

    1. Parses Netscape rows into Playwright-format cookies.
    2. Merges into any existing ``auth.json`` at ``auth_path`` — preserving
       localStorage (reese84) and non-HEB cookies.
    3. Writes back with secure (0600) permissions.

    Args:
        cookies_text: Full contents of a Netscape-format ``cookies.txt`` export.
        auth_path: Destination ``auth.json`` (Playwright storage-state format).

    Returns:
        Summary dict with ``cookies_written``, ``skipped_rows``, and paths.

    Raises:
        CookiesTxtParseError: If the text has no parseable cookie rows.
    """
    auth_path = Path(auth_path).expanduser()

    parsed = parse_netscape_cookies(cookies_text)

    # Preserve any existing localStorage (reese84 lives here, and manual
    # bookmarklet captures often land it via a separate step).
    existing: dict[str, Any] | None = None
    if auth_path.exists():
        try:
            existing = json.loads(auth_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(
                "Existing auth.json unreadable; will overwrite",
                path=str(auth_path),
                error=str(e),
            )
            existing = None

    state = merge_into_storage_state(parsed["cookies"], existing)

    auth_path.parent.mkdir(parents=True, exist_ok=True)

    # Reuse the project's secure-writer so we get 0600 perms consistently.
    from texas_grocery_mcp.utils.secure_file import write_secure_json

    write_secure_json(auth_path, state)

    # parse_netscape_cookies already restricts rows to _ALLOWED_DOMAINS, so
    # every parsed cookie is HEB's.
    heb_written = len(parsed["cookies"])
    logger.info(
        "Loaded cookies from Netscape text",
        auth_path=str(auth_path),
        cookies_written=heb_written,
        cookies_total=len(parsed["cookies"]),
        skipped_rows=parsed["skipped"],
    )

    return {
        "cookies_written": heb_written,
        "cookies_total_in_file": len(parsed["cookies"]),
        "skipped_rows": parsed["skipped"],
        "auth_path": str(auth_path),
        "preserved_localstorage": bool(existing and existing.get("origins")),
    }


def load_cookies_txt(
    cookies_txt_path: Path,
    auth_path: Path,
) -> dict[str, Any]:
    """Read a Netscape ``cookies.txt`` file and write ``auth.json`` in Playwright format.

    Thin file-reading wrapper around ``load_cookies_text`` for callers that
    have a path rather than the file's contents (e.g. tests, or a local
    script).

    Args:
        cookies_txt_path: File the user exported from their real browser.
        auth_path: Destination ``auth.json`` (Playwright storage-state format).

    Returns:
        Summary dict with ``cookies_written``, ``skipped_rows``, and paths.

    Raises:
        FileNotFoundError: If ``cookies_txt_path`` doesn't exist.
        CookiesTxtParseError: If the file has no parseable cookie rows.
    """
    cookies_txt_path = Path(cookies_txt_path).expanduser()

    if not cookies_txt_path.exists():
        raise FileNotFoundError(f"cookies.txt not found: {cookies_txt_path}")

    text = cookies_txt_path.read_text(encoding="utf-8")
    result = load_cookies_text(text, auth_path)
    result["cookies_txt_path"] = str(cookies_txt_path)
    return result
