# Troubleshooting Guide

This guide covers common issues, credential discovery mechanisms, platform differences, and diagnostic steps for `ai-usage-monitor` across **Cursor**, **OpenAI Codex**, and **Google Antigravity**.

---

## 1. Quick Diagnostics: `usage doctor`

Always start troubleshooting by running the diagnostic tool:

```bash
uv run usage doctor
```

`usage doctor` checks prerequisite binaries, credential stores, token freshness, and connectivity across all supported providers.

Example output:
```text
Codex
  [ok] codex binary found: /opt/homebrew/bin/codex
  [ok] auth file found: /Users/username/.codex/auth.json
  [ok] OAuth access token present
  [ok] token is fresh (expires in 54h 11m)

Cursor
  [ok] desktop state.vscdb found: /Users/username/Library/Application Support/Cursor/User/globalStorage/state.vscdb
  [ok] desktop access token present in state.vscdb
  [ok] desktop token is fresh (expires in 1439h 16m)
  [ok] Cursor CLI binary found: /Users/username/.local/bin/cursor
  [ok] CLI credentials found (keychain)
  [ok] CLI token is fresh (expires in 598h 49m)

Antigravity
  [ok] agy found: /Users/username/.local/bin/agy
  [ok] `agy --print /usage` returned quota
```

---

## 2. Cursor Troubleshooting

`ai-usage-monitor` supports environments with **Cursor Desktop only**, **Cursor CLI only** (e.g., remote SSH machines, Docker, headless Linux), or **both installed**.

### 2.1 Credential Discovery Locations

#### Cursor Desktop (`state.vscdb`)
Cursor Desktop stores session state in an SQLite database.
* **macOS**: `~/Library/Application Support/Cursor/User/globalStorage/state.vscdb`
* **Windows**: `%APPDATA%\Cursor\User\globalStorage\state.vscdb`
* **Linux**: `~/.config/Cursor/User/globalStorage/state.vscdb` (or `$XDG_CONFIG_HOME/Cursor/User/globalStorage/state.vscdb`)

`ai-usage-monitor` opens `state.vscdb` in read-only mode (`mode=ro`) with a small busy timeout and queries `cursorAuth/accessToken` and `cursorAuth/cachedEmail` from `ItemTable`.

#### Cursor CLI (`cursor agent` / `agent`)
Cursor CLI uses an independent credential manager:
1. **macOS (System Keychain)**:
   * By default, Cursor CLI stores tokens in the macOS login keychain:
     * Access Token: Service `cursor-access-token`, Account `cursor-user`
     * Refresh Token: Service `cursor-refresh-token`, Account `cursor-user`
   * You can manually verify the presence of the access token in your terminal:
     ```bash
     security find-generic-password -s cursor-access-token -a cursor-user -w
     ```
2. **File Storage (`auth.json`)**:
   * Used on Linux, Windows, or when `AGENT_CLI_CREDENTIAL_STORE=file`:
     * macOS: `~/.cursor/auth.json`
     * Windows: `%APPDATA%\Cursor\auth.json`
     * Linux: `~/.config/cursor/auth.json` (or `~/.cursor/auth.json`)
3. **User Profile Cache (`cli-config.json`)**:
   * `~/.cursor/cli-config.json` stores user profile info (`email`, `displayName`, `userId`) under `authInfo`.

### 2.2 Common Issues & Resolutions

#### Issue: "Cursor credentials not found in Desktop database or CLI credential store"
* **Cause**: Neither Cursor Desktop nor Cursor CLI has an active login session on this machine.
* **Resolution**:
  * If using Cursor Desktop: Open Cursor, ensure you are signed in, and allow it to initialize.
  * If using Cursor CLI: Run `cursor login` (or `agent login`) to authenticate in your browser or terminal.
  * Alternatively, provide a manual session cookie:
    ```bash
    uv run usage cursor --cookie "WorkosCursorSessionToken=..."
    # or set in environment:
    export LLM_USAGE_CURSOR_COOKIE="WorkosCursorSessionToken=..."
    ```

#### Issue: "Cursor desktop access token in state.vscdb has expired"
* **Cause**: The JWT `exp` timestamp in `state.vscdb` is in the past or within 60 seconds of expiration.
* **Resolution**: Focus or restart Cursor Desktop. Cursor automatically refreshes its access token upon window focus.

#### Issue: "Cursor CLI access token has expired"
* **Cause**: The stored CLI access token expired and requires a fresh session.
* **Resolution**: Run `cursor login` (or `agent status`) to trigger token refresh.

#### Issue: Selecting an explicit source
If both Desktop and CLI are installed, `usage` will check Desktop first, then CLI. You can force a specific source:
```bash
# Force Desktop state database:
uv run usage cursor --source desktop

# Force Cursor CLI credentials:
uv run usage cursor --source cli
```

---

## 3. OpenAI Codex Troubleshooting

### 3.1 Credential Discovery
1. **Primary: OAuth via `auth.json`**:
   * Evaluates `CODEX_HOME/auth.json` if the environment variable is set.
   * Fallback on Windows: `%USERPROFILE%\.codex\auth.json`
   * Fallback on macOS/Linux: `~/.codex/auth.json`
   * If the OAuth access token is valid and fresh, calls `GET https://chatgpt.com/backend-api/wham/usage`.
2. **Fallback: `codex app-server` RPC**:
   * If `auth.json` is missing or the token is stale, `ai-usage-monitor` launches `codex -s read-only -a never app-server` in the background and queries `account/rateLimits/read` via JSON-RPC.

### 3.2 Common Issues & Resolutions

#### Issue: "auth file missing at: ~/.codex/auth.json"
* **Resolution**: Run `codex` interactively in your terminal to sign into your OpenAI / ChatGPT account. This will generate `~/.codex/auth.json`.

#### Issue: "access token is stale; will require CLI RPC refresh"
* **Resolution**: Ensure the `codex` executable is on your `PATH`. When present, `ai-usage-monitor` invokes the background RPC server to query usage without manual re-login.

---

## 4. Google Antigravity Troubleshooting

### 4.1 Discovery & Quota Retrieval
* Resolves the `agy` binary (`agy` or `agy.exe`) on `PATH` or at `~/.local/bin/agy`.
* Runs `agy --print /usage` non-interactively and parses the quota table for Gemini and Claude/GPT usage pools (5-hour and weekly).
* On Windows, launches with `CREATE_NO_WINDOW` to prevent console window flicker.

### 4.2 Common Issues & Resolutions

#### Issue: "agy binary not found on PATH"
* **Resolution**:
  * Verify that Google Antigravity CLI is installed.
  * Ensure the directory containing `agy` is in your `PATH` (e.g. `export PATH="$HOME/.local/bin:$PATH"`).
  * Or specify the binary path explicitly in config:
    ```toml
    [antigravity]
    cli_path = "/path/to/agy"
    ```
    or via environment variable:
    ```bash
    export LLM_USAGE_ANTIGRAVITY_CLI="/path/to/agy"
    ```

#### Issue: "`agy --print /usage` failed: not logged in"
* **Resolution**: Run `agy` in your terminal and complete the authentication flow.

---

## 5. Exit Codes & Programmatic Use

When writing scripts or automating alerts, `usage` produces standard exit codes:

| Exit Code | Meaning | Example Causes |
|---|---|---|
| `0` | Success | All requested provider usages fetched successfully. |
| `1` | General Failure | Unknown error or provider schema mismatch. |
| `2` | Partial Success | In `usage all`, at least one provider succeeded while another failed. |
| `3` | Authentication Error | Expired token, unauthenticated session, invalid cookie. |
| `4` | Network / Timeout | Connection refused, HTTP 5xx, or network timeout exceeded. |
| `5` | Prerequisite Missing | Binary or credential file not found. |

To inspect raw data programmatically, use the `--json` flag:
```bash
uv run usage --json
uv run usage cursor --json
```
