# AI Usage Monitor CLI Tool

## Documentation & References

- Refer to [the troubleshooting guide](docs/troubleshooting.md) for diagnostics, credential discovery, and common issues.
- Algorithm details were close or similar to what [CodexBar](https://codexbar.app/) uses.
- Refer to [the algorithm detail document](docs/llm_subs_usage_algo_win.md)

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

## Architectural Details & Platform Differences

### Antigravity: Windows vs. macOS/Linux (CodexBar)

Users transitioning from macOS/Linux [CodexBar](https://github.com/steipete/CodexBar) to Windows 11 may wonder why background process behavior differs or why an additional instance might be observed:

1. **Use the official `agy /usage` command**:
   - `ai-usage-monitor` invokes `agy --print /usage` and parses its tab-separated quota rows. The official command performs silent keyring authentication and retrieves the same quota summary shown by Antigravity.
   - This avoids depending on Antigravity's private loopback RPC authentication, whose CSRF-token behavior differs between app and CLI versions.

2. **Windows Console Subsystem (`CREATE_NO_WINDOW`)**:
   - On Windows, `agy.exe` is compiled as a Console subsystem binary (`IMAGE_SUBSYSTEM_WINDOWS_CUI`). Spawning it without special flags can allocate or attach a visible console context.
   - `ai-usage-monitor` runs the print-mode command with `stdin=subprocess.DEVNULL` and `creationflags=subprocess.CREATE_NO_WINDOW`, keeping the one-shot lookup silent and ensuring the process is cleaned up after the quota is read.

3. **No desktop-process reuse**:
   - Antigravity Desktop and IDE instances expose private, dynamically assigned loopback services with version-specific CSRF requirements.
   - The provider deliberately uses the official `agy` command instead of probing arbitrary `language_server.exe` ports, so the result follows the same authenticated path as `/usage`.


