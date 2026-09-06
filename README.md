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

## Architectural Details & Platform Differences

### Antigravity: Windows vs. macOS/Linux (CodexBar)

Users transitioning from macOS/Linux [CodexBar](https://github.com/steipete/CodexBar) to Windows 11 may wonder why background process behavior differs or why an additional instance might be observed:

1. **Direct Google OAuth API vs. Local Loopback Probe**:
   - On macOS/Linux, CodexBar supports an optional remote OAuth fetch mode: it reads stored OAuth tokens (`~/.codexbar/antigravity/oauth_creds.json` or macOS Keychain) and directly calls Google's Cloud Code / Code Assist quota endpoints (`daily-cloudcode-pa.googleapis.com`) over HTTPS. When operating in remote mode, **no local CLI process is spawned**.
   - `ai-usage-monitor` prioritizes querying the official local Language Server (`/exa.language_server_pb.LanguageServerService/RetrieveUserQuotaSummary`) because it provides the richest real-time rate-limit breakdown (5-hour session buckets, weekly buckets, and reset descriptions).

2. **POSIX PTY vs. Windows Console Subsystem (`CREATE_NO_WINDOW`)**:
   - When CodexBar falls back to running `agy` locally on macOS/Linux, it spawns `agy` inside an allocated POSIX pseudoterminal (PTY via `openpty`/`forkpty`). Unix background processes in detached PTYs have zero graphical footprint (no Dock icon, no terminal window).
   - On Windows, `agy.exe` is compiled as a Console subsystem binary (`IMAGE_SUBSYSTEM_WINDOWS_CUI`). Spawning it without special flags causes Windows to allocate or attach a console context, which could briefly flicker a console host window or appear prominently in Task Manager.
   - `ai-usage-monitor` handles this by launching cold-start sessions with `stdin=subprocess.DEVNULL` and `creationflags=subprocess.CREATE_NO_WINDOW`, ensuring completely silent, invisible background execution that terminates cleanly immediately after reading quota.

3. **Multi-Process Discovery (`agy`, `antigravity`, `language_server`)**:
   - If you already have an Antigravity Desktop app or VS Code extension running, its embedded service is named `language_server.exe` (located at `%LOCALAPPDATA%\Programs\antigravity\resources\bin\language_server.exe`).
   - `ai-usage-monitor` scans listening ports across `agy.exe`, `antigravity.exe`, and `language_server.exe` using the Windows IP Helper API (`GetExtendedTcpTable`). If an IDE or existing CLI session is active, its port is **reused immediately without spawning an additional process**.


