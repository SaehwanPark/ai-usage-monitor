# AI Usage Monitor CLI Tool

## Algorithmic References

- Algorithm details were close or similar to what [CodexBar](https://codexbar.app/) uses.
- Refer to [the algorithm detail document](docs\llm_subs_usage_algo_win.md)

## Development Coding Rules

- 2 spaces of tabsize throughout
- `uv` for Python and ecosystem management
- Functional programming paradigm preferred
- Test-driven development preferred (use `pytest`)
- Spec-driven development preferred
- Simple and straight coding practices preferred
- Type-safity preferred (use `basedpyright`)
- Respect good recommendations from the "Clean Code" book

## CLI Usage

Run using `uv run usage` or `uv run ai-usage-monitor`:

```powershell
# Display all providers (Codex, Cursor, Antigravity)
uv run usage

# Inspect specific provider
uv run usage codex
uv run usage cursor
uv run usage antigravity

# Get normalized JSON output
uv run usage --json
uv run usage codex --json
uv run usage antigravity --json

# Run local diagnostic health check
uv run usage doctor
```

### Options and Flags

- `--json`: Output normalized JSON
- `--timeout <seconds>`: Network and process startup timeout (default: 10.0s)
- `--cookie <cookie>`: Manual Cursor session cookie header override
- `--source <oauth|cli|agy>`: Provider retrieval source override
- `--codex-home <path>`: Override path to `CODEX_HOME` directory
- `--verbose`: Enable diagnostic details (secrets are always redacted)

### Configuration

Optional configuration file: `%APPDATA%\llm-usage\config.toml`

```toml
[codex]
home = "C:/custom/codex"

[cursor]
cookie = "WorkosCursorSessionToken=..."

[antigravity]
cli_path = "C:/custom/agy.exe"
```

Environment variable overrides:
- `CODEX_HOME`
- `LLM_USAGE_CURSOR_COOKIE`
- `LLM_USAGE_ANTIGRAVITY_CLI`
- `LLM_USAGE_TIMEOUT`

