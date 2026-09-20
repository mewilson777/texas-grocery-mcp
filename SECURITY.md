# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in Texas Grocery MCP, please report it responsibly:

1. **Do NOT** open a public GitHub issue for security vulnerabilities
2. Email the maintainer directly or use GitHub's private vulnerability reporting feature
3. Include as much detail as possible:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

## Security Considerations

### Credential Storage

Saving HEB credentials (via `session_save_credentials`) is **optional** - it
exists only to let `session_refresh` attempt an automatic login. Cookie import
via `session_load_cookies` is the recommended workflow and requires no stored
credentials at all.

When you do save them, the OS keyring is used first:

- **macOS**: Keychain
- **Windows**: Windows Credential Manager
- **Linux**: Secret Service API (GNOME Keyring, KWallet)

**Fallback:** if no working keyring backend is available (common on headless
Linux), credentials fall back to a Fernet-encrypted file at
`~/.texas-grocery-mcp/.credentials.enc`, with the encryption key alongside it
at `~/.texas-grocery-mcp/.credentials.key`. Both are written with owner-only
(0o600) permissions.

Be aware of what that fallback means: the key sits next to the ciphertext, so
it protects against casual disclosure (a backup, a shared screen, a stray
`cat`) but **not** against anyone who can already read your home directory as
you. `session_status` reports which method is in use via
`credential_storage_method`. If that says the encrypted-file fallback and you
aren't comfortable with the tradeoff, use `session_clear_credentials()` and
stick to cookie import.

### Session Data

Session data (cookies, tokens) is stored in `~/.texas-grocery-mcp/auth.json`. This file:

- Contains authentication tokens for HEB.com (including the `reese84`
  bot-detection token and your HEB session cookies)
- Is written with owner-only (0o600) permissions via `utils/secure_file.py`
- Is excluded from version control via `.gitignore`

Treat `auth.json` as equivalent to being logged into your HEB account. Anyone
who can read it can act as you on heb.com until the session expires.

### Network Security

- All API calls use HTTPS
- No sensitive data is logged at INFO level
- Debug logging may include request/response data (use with caution)

### Human-in-the-Loop

`session_refresh` can hand control back to you rather than trying to defeat
HEB's protections on its own. When it hits a login form, CAPTCHA, 2FA prompt,
or WAF interstitial, it returns `status: "human_action_required"` with an
`action` and a `screenshot_path`, leaves the browser open, and waits for you
to act before continuing.

This is deliberate. This project does not attempt to solve CAPTCHAs or evade
bot detection - where HEB asks for a human, a human answers.

## Best Practices for Users

1. **Keep dependencies updated**: Run `pip install --upgrade texas-grocery-mcp` regularly
2. **Protect auth files**: Ensure `~/.texas-grocery-mcp/` has appropriate permissions (700)
3. **Use environment variables**: Store sensitive configuration in environment variables, not config files

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Dependency Security

We monitor dependencies for known vulnerabilities. If you notice a vulnerable dependency:

1. Check if an update is available
2. Open an issue or PR with the fix
3. For critical vulnerabilities, report privately
