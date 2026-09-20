# Troubleshooting Guide

This guide covers common issues and their solutions when using the Texas Grocery MCP.

## Table of Contents

- [Session & Authentication Issues](#session--authentication-issues)
- [Product Search Issues](#product-search-issues)
- [Store Issues](#store-issues)
- [Network & API Issues](#network--api-issues)
- [Installation Issues](#installation-issues)

---

## Session & Authentication Issues

### "Session expired" / "needs_refresh: true"

**Symptoms:**
- `session_status` shows `authenticated: false` or `needs_refresh: true`
- Operations return "Login required" errors

**Solution (recommended - reliable):**
```
1. Log in to heb.com in your own regular browser
2. Export cookies for heb.com (e.g. with "Get cookies.txt LOCALLY")
3. Call session_load_cookies(cookies_txt="<pasted export>")
4. Call session_status to confirm
```

**Fallback (session_refresh) - HEB's bot detection frequently blocks this
regardless of headless mode; don't expect it to work reliably:**
```
1. Call session_refresh() - opens a visible browser
2. Complete login/CAPTCHA in that window if prompted
3. Tell the assistant "done" when you've logged in
4. The assistant will call session_refresh() again to save the session
5. If it keeps failing, switch to the cookie-import solution above
```

---

### "Security challenge detected" / WAF Block

**Symptoms:**
- `security_challenge_detected: true` in search results
- Browser shows "Please verify you are human"
- Screenshot shows hCaptcha, "Additional security check required", or a
  proxy/VPN block message

**Cause:** HEB's Web Application Firewall (WAF) detected automated access.
This can also be triggered by a burst of rapid/automated requests from your
IP (repeated failed logins, tight retry loops) - if so, it may take a
cooldown period before your IP is trusted again, independent of anything you
change here.

**Solution (recommended - reliable):** Same cookie-import steps as above -
a fresh, legitimately-obtained cookie export is far less likely to trip the
WAF than another automated login attempt.

**Fallback (session_refresh):**
```
1. Call session_refresh() - opens a visible browser
2. Solve the CAPTCHA in the browser window if one appears
3. Navigate around the site briefly (search for a product, click a category)
4. Tell the assistant "done"
```

**Prevention:**
- Don't retry `session_refresh` repeatedly after it fails - that's more
  likely to reinforce a WAF block than clear it
- Don't make too many rapid requests
- Use `product_search_batch` instead of many individual searches
- Keep your session refreshed (don't let it expire completely)

---

### "Could not find login form" Error

**Symptoms:**
- `session_refresh` returns `error: login_form_not_found`
- Screenshot shows unexpected page content

**Causes:**
- HEB changed their login page structure
- Network issue caused incomplete page load
- WAF blocked the request before login page loaded

**Solution:**
```
1. Check the screenshot to see what loaded
2. Try session_refresh(headless=False, timeout=60000) with longer timeout
3. If WAF page shows, solve it first, then retry
4. If still failing, try session_clear() then session_refresh(headless=False)
```

---

### Credentials Not Working

**Symptoms:**
- `session_save_credentials` succeeded but auto-login fails
- "Invalid credentials" error during login

**Solution:**
```
1. Verify your HEB.com credentials work by logging in manually at heb.com
2. Check for typos in email/password
3. Clear and re-save credentials:
   - session_clear_credentials()
   - session_save_credentials(email="your@email.com", password="yourpassword")
4. Test with session_refresh()
```

---

## Product Search Issues

### "No products found" / Empty Results

**Symptoms:**
- `product_search` returns `count: 0` and `data_source: none`, with a `note`
  and `fallback_reason` explaining why
- Or it returns `data_source: typeahead_suggestions` (only when
  `TYPEAHEAD_FALLBACK_ENABLED=true`), meaning names with no real prices or IDs

**Causes:**
- Query too specific or misspelled
- Store doesn't carry the product
- Session expired, so the authenticated SSR search failed. Typeahead fallback
  is **off by default**, so this surfaces as zero products rather than as
  placeholder suggestions - read `fallback_reason` to tell the two apart

**Solutions:**

1. **Try broader search terms:**
   - Instead of "HEB Organics Whole Milk 1 Gallon" try "organic milk"
   - Instead of "boneless skinless chicken breast" try "chicken breast"

2. **Check store availability:**
   ```
   store_search("your address")
   store_change("store_id_from_results")
   product_search("your query")
   ```

3. **Refresh session if data_source is "typeahead_suggestions":**
   ```
   session_load_cookies(cookies_txt="<fresh export from your browser>")
   product_search("your query")
   ```

---

### "No product_id available"

**Symptoms:**
- Product has `_warning: "No product_id available. Try a more specific search or refresh session."`
- `product_id` starts with "suggestion-"

**Cause:** The search fell back to typeahead suggestions which don't have real product IDs.

**Solution:**
```
1. Refresh your session: session_load_cookies(cookies_txt="<fresh export>")
2. Search again with the same query
3. If still getting suggestions, try a more specific query
4. Or use product_get with a known product_id
```

---

### Search Returns "price: null"

**Symptoms:**
- Products have `price: null` or no pricing info

**Cause:** Not authenticated or store not set.

**Solution:**
```
1. Check session: session_status()
2. If not authenticated: session_load_cookies(cookies_txt="<fresh export>")
3. Set a store: store_change("store_id")
4. Search again
```

---

## Store Issues

### `store_change` Fails

**Symptoms:**
- `store_change` returns `code: INVALID_STORE_ID`, `STORE_CHANGE_FAILED`,
  or `NOT_AUTHENTICATED`

**Causes and solutions:**

- `INVALID_STORE_ID` - the ID isn't one HEB recognizes. Get a real one from
  `store_search("your address")` rather than guessing.
- `NOT_AUTHENTICATED` - no valid session. Import cookies first:
  `session_load_cookies(cookies_txt="<fresh export>")`.
- `STORE_CHANGE_FAILED` - HEB rejected or didn't apply the change. This is
  most often the WAF distrusting an API call that didn't originate from the
  live browser session that logged in, so it can happen immediately after a
  *successful* `session_load_cookies`. Re-import a fresh cookie export and
  retry; if it persists, change your store on heb.com directly and then call
  `store_change` with the same ID to sync the local default.

**Note:** when you aren't authenticated, `store_change` doesn't fail - it sets
a *local* default for product searches only and returns
`method: "local_only"` with a `warning`. Check that field if you expected the
change to reach your HEB.com account.

---

### "Geocoding failed" / Can't Find Stores

**Symptoms:**
- `store_search` returns no results
- Error mentions geocoding failure

**Causes:**
- Address not recognized
- Geocoding service unavailable

**Solutions:**

1. **Try different address formats:**
   - Full address: "1234 Main St, Austin, TX 78701"
   - Just zip code: "78701"
   - City and state: "Austin, TX"

2. **Use a bundled store ID directly:** these ship in `KNOWN_STORES` and are
   used as the fallback suggestion when no default store is set:
   ```
   store_change("737")  # The Heights H-E-B (Houston)
   store_change("579")  # Buffalo Speedway H-E-B (Houston)
   store_change("150")  # Montrose H-E-B (Houston)
   ```

---

## Network & API Issues

### Timeout Errors

**Symptoms:**
- Operations fail with timeout errors
- "Connection timed out" messages

**Solutions:**
```
1. Check your internet connection
2. Try again - HEB's servers may be slow
3. For session_refresh, increase timeout:
   session_refresh(headless=False, timeout=60000)
```

---

### "Circuit breaker open"

**Symptoms:**
- Multiple operations fail in a row, immediately and without a network delay

**Cause:** Too many consecutive failures triggered the circuit breaker.

**Solution:**
```
1. Wait 30 seconds for the circuit breaker to recover
   (CIRCUIT_BREAKER_TIMEOUT, default 30s)
2. Retry your operation - the breaker lets a trial request through
   once the timeout has elapsed
3. If it reopens immediately, the underlying problem is still there:
   check session_status() and your network connection
```

---

## Installation Issues

### "Playwright not installed"

**Symptoms:**
- `session_refresh` says Playwright not available
- Browser-based features don't work

**Solution:**
```bash
# Install with browser support
pip install texas-grocery-mcp[browser]

# Or with uv:
uv pip install texas-grocery-mcp[browser]

# Install browser binaries
playwright install chromium
```

---

### "Chromium not found"

**Symptoms:**
- Session refresh fails to launch browser
- Error mentions missing Chromium

**Solution:**
```bash
playwright install chromium
```

---

## Error Code Reference

| Code | Emitted by | Meaning | Solution |
|------|------------|---------|----------|
| `NO_STORE_SET` | `product_search` | No default store configured | Use `store_change("store_id")` |
| `INVALID_PRODUCT_ID` | `product_get` | Product ID is malformed, or is a `suggestion-` placeholder | Use an ID from `product_search` results |
| `PRODUCT_NOT_FOUND` | `product_get` | HEB returned no product for that ID | Verify the product ID |
| `FETCH_ERROR` | `product_get` | Network/API error | Check connection, retry |
| `NOT_AUTHENTICATED` | `store_change` | No valid session | `session_load_cookies(cookies_txt=...)` |
| `INVALID_STORE_ID` | `store_change` | HEB doesn't recognize that store ID | Get one from `store_search` |
| `STORE_CHANGE_FAILED` | `store_change` | HEB rejected or didn't apply the change | See [`store_change` Fails](#store_change-fails) |
| `LOGIN_REQUIRED` | auto-refresh | Session expired and couldn't be refreshed | `session_load_cookies(cookies_txt=...)` |
| `HUMAN_ACTION_REQUIRED` | auto-refresh | Refresh hit a login form, CAPTCHA, 2FA, or WAF page | Check `screenshot_path`, then prefer cookie import |

---

## Getting More Help

If you're still stuck:

1. **Check session status:** `session_status()` - provides diagnostic info
2. **Inspect the search diagnostics:** `product_search` returns `data_source`,
   `authenticated`, `attempts`, and (when relevant) `fallback_reason` and
   `search_url`, which show exactly which query variations and methods were tried
3. **Enable debug logging:** Set `LOG_LEVEL=DEBUG` environment variable
   (logs go to stderr)
4. **Report issues:** https://github.com/mgwalkerjr95/texas-grocery-mcp/issues

When reporting issues, include:
- The error message/code
- Output from `session_status()`
- What you were trying to do
- Any screenshots if session_refresh provided them
