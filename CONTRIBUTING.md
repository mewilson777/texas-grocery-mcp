# Contributing to Texas Grocery MCP

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Getting Started

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/texas-grocery-mcp
   cd texas-grocery-mcp
   ```
3. Install development dependencies:
   ```bash
   pip install -e ".[dev]"
   playwright install chromium
   ```

## Development Workflow

### Tests

There is currently **no test suite** in this repository. The previous unit
tests were removed because their mocked HTTP fixtures had drifted from HEB's
live behavior - which is the thing this project actually has to survive - and
passing tests against stale mocks were worse than no tests.

If you want to reintroduce tests, that's welcome, but please open an issue to
discuss the approach first. Fixtures captured from real HEB responses (and
refreshed when they break) are far more useful here than hand-written mocks.

### Code Quality

Before submitting a PR, ensure your code passes all checks:

```bash
# Linting
ruff check src

# Type checking (strict mode - see [tool.mypy] in pyproject.toml)
mypy src

# Auto-fix what ruff can
ruff check src --fix
```

Both of these run in CI on Python 3.11 and 3.12.

### Project Structure

```
src/texas_grocery_mcp/
├── auth/           # Session state, cookie import, browser login, credentials
├── clients/        # HEB GraphQL + SSR client (the core of the project)
├── models/         # Pydantic data models
├── observability/  # structlog setup - logs to stderr, never stdout
├── reliability/    # Caching, throttling, retry, circuit breaker
├── services/       # Geocoding (Nominatim)
├── tools/          # MCP tool implementations
├── utils/          # Settings (pydantic-settings) and secure file writes
├── state.py        # Cross-request state (default store, cached stores)
└── server.py       # Main MCP server entry point
```

Two constraints that are easy to violate by accident:

- **Never write to stdout.** stdout carries the MCP protocol. Use the
  `structlog` logger from `observability/logging.py`, which emits JSON to
  stderr. No `print()`.
- **Write auth state and credentials through `utils/secure_file.py`**, not
  raw `json.dump` - it sets owner-only (0o600) permissions.

## Submitting Changes

1. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes and commit:
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   ```

3. Push to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```

4. Open a Pull Request against `main`

### Commit Message Format

We follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `test:` - Adding or updating tests
- `refactor:` - Code refactoring
- `chore:` - Maintenance tasks

## A Note on HEB's Endpoints

This project talks to HEB's *unofficial* web endpoints - Next.js SSR pages and
a GraphQL API with persisted query hashes - not a public API. Two consequences
for contributors:

- **Persisted query hashes and SSR parsing break silently** when HEB ships a
  frontend change. That's the expected failure mode behind most bugfix commits
  here. If store or product search suddenly returns nothing, suspect this first.
- **Prefer settings over constants.** Throttling, retry, and circuit-breaker
  behavior are all `Settings` fields in `utils/config.py` so they can be tuned
  by environment variable. Add a setting rather than a new hardcoded number.

## Code Style

- Follow PEP 8 (enforced by ruff)
- Use type hints for all function signatures
- Keep functions focused and small
- Document complex logic with comments
- Use meaningful variable and function names

## Reporting Issues

When reporting bugs, please include:

1. Python version
2. Operating system
3. Steps to reproduce
4. Expected vs actual behavior
5. Relevant error messages or logs

## Questions?

Feel free to open an issue for questions or discussions about the project.
