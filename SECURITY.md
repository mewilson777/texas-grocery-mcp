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

This MCP stores credentials securely using the system keyring:

- **macOS**: Keychain
- **Windows**: Windows Credential Manager
- **Linux**: Secret Service API (GNOME Keyring, KWallet)

Credentials are never stored in plain text files.

### Session Data

Session data (cookies, tokens) is stored in `~/.texas-grocery-mcp/auth.json`. This file:

- Contains authentication tokens for HEB.com
- Should be protected with appropriate file permissions
- Is excluded from version control via `.gitignore`

### Network Security

- All API calls use HTTPS
- No sensitive data is logged at INFO level
- Debug logging may include request/response data (use with caution)

### Human-in-the-Loop

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
