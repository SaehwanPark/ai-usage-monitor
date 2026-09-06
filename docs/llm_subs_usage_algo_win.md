# Windows CLI Subscription Usage Monitor
## Algorithmic design notes derived from CodexBar for OpenAI Codex, Cursor, and Antigravity

**Purpose:** implementation handoff for a new **Windows-first, CLI-only** tool that reports current subscription usage for exactly these providers:

- OpenAI Codex / ChatGPT-backed Codex subscription limits
- Cursor
- Google Antigravity

**Reference implementation studied:** `steipete/CodexBar`  
**Reference revision:** `211781be79d37fd942bc4ee623abd6d5c8baeffd` (current `main` when analyzed on 2026-09-05)  
**CodexBar license:** MIT

This is not a proposal to port CodexBar's UI. It extracts the smallest reliable mechanisms needed to answer:

> "How much of my current subscription quota have I used, and when does it reset?"

The recommended tool should be provider-focused, Windows-native, read-only with respect to provider-owned credentials, scriptable, and safe to run frequently.

---

# 1. Executive design

Use a provider adapter model with one normalized result:

```text
usage.exe
  -> discover provider credentials/session
  -> fetch provider quota
  -> normalize provider-specific quota windows
  -> print human text or stable JSON
```

Recommended automatic strategy:

| Provider | Preferred Windows source | Fallback | Why |
|---|---|---|---|
| Codex | Read Codex OAuth credentials and call `wham/usage` | `codex app-server` JSON-RPC | Structured first-party data; CLI remains credential refresh owner |
| Cursor | Read Cursor desktop `state.vscdb`, derive web session cookie, call Cursor dashboard APIs | User-supplied cookie header | Avoid browser-cookie decryption and browser automation |
| Antigravity | Run/reuse `agy`, discover its localhost port, call quota endpoint | Legacy localhost endpoints; optional OAuth later | Richest observed quota data, including 5-hour and weekly pools |

Do **not** make browser scraping, DOM parsing, UI automation, or browser-cookie extraction part of v1.

The main architectural rule is:

> Separate **credential/session acquisition** from **quota fetching** from **normalization**.

That lets provider internals change without changing the CLI's public result schema.

---

# 2. Product scope

## 2.1 Required commands

A minimal interface:

```powershell
usage
usage all
usage codex
usage cursor
usage antigravity

usage --json
usage cursor --json
usage antigravity --verbose
usage doctor
```

Useful optional flags:

```powershell
usage --no-cache
usage --timeout 10
usage cursor --cookie "..."
usage codex --source oauth
usage codex --source cli
usage antigravity --source agy
```

Prefer configuration through a small config file and environment variables rather than many required flags.

Suggested config location:

```text
%APPDATA%\llm-usage\config.toml
```

Suggested environment overrides:

```text
LLM_USAGE_CURSOR_COOKIE
LLM_USAGE_ANTIGRAVITY_CLI
CODEX_HOME
```

## 2.2 Explicitly out of scope for v1

- Menu-bar UI
- Browser automation
- Browser cookie database decryption
- Cost reconstruction from local prompts
- Provider status/incidents
- Multi-machine aggregation
- Purchasing or redeeming credits
- Changing provider account state
- Refreshing or rewriting Codex-owned `auth.json`
- Parsing the rendered Codex or `agy` TUI

---

# 3. Normalized usage model

All providers should normalize to this shape before formatting:

```json
{
  "provider": "codex",
  "account": {
    "id": null,
    "email": "user@example.com",
    "plan": "pro"
  },
  "source": "oauth",
  "windows": [
    {
      "id": "session",
      "label": "5-hour",
      "used_percent": 15.0,
      "remaining_percent": 85.0,
      "window_seconds": 18000,
      "resets_at": "2026-09-05T23:00:00Z",
      "usage_known": true
    },
    {
      "id": "weekly",
      "label": "Weekly",
      "used_percent": 5.0,
      "remaining_percent": 95.0,
      "window_seconds": 604800,
      "resets_at": "2026-09-10T00:00:00Z",
      "usage_known": true
    }
  ],
  "credits": null,
  "fetched_at": "2026-09-05T22:30:00Z",
  "warnings": []
}
```

## 3.1 Normalization rules

Use these invariants everywhere:

```text
used_percent      := clamp(provider_used_percent, 0, 100)
remaining_percent := 100 - used_percent
```

If provider data is expressed as a remaining fraction:

```text
remaining_percent := clamp(remaining_fraction * 100, 0, 100)
used_percent      := 100 - remaining_percent
```

Do not silently substitute `0% used` for unknown usage.

Represent unknown explicitly:

```json
{
  "usage_known": false,
  "used_percent": null
}
```

All reset timestamps should be stored internally as UTC instants. Human formatting may use local time.

---

# 4. OpenAI Codex

## 4.1 Recommended source order

For this Windows CLI:

```text
AUTO
  1. OAuth usage API using Codex-owned auth.json
  2. Codex app-server JSON-RPC
  3. fail with actionable authentication/install guidance
```

This differs slightly from CodexBar's own CLI default because this tool does not need CodexBar's optional OpenAI web-dashboard extras.

The OAuth API is the cleanest path. The app-server fallback is important because the Codex CLI owns authentication refresh.

---

## 4.2 Credential discovery

CodexBar reads:

```text
$CODEX_HOME\auth.json
```

when `CODEX_HOME` is explicitly set; otherwise use:

```text
%USERPROFILE%\.codex\auth.json
```

Expected shape:

```json
{
  "OPENAI_API_KEY": null,
  "tokens": {
    "id_token": "eyJ...",
    "access_token": "eyJ...",
    "refresh_token": "...",
    "account_id": "account-..."
  },
  "last_refresh": "2026-09-01T12:34:56Z"
}
```

Read it **only**.

Do not:

- replace the access token;
- redeem the refresh token;
- rewrite `last_refresh`;
- change `account_id`;
- normalize or reserialize the file.

This file is owned by Codex.

### Credential resolution

```pseudo
function load_codex_credentials():
  home =
    if env.CODEX_HOME is nonempty:
      env.CODEX_HOME
    else:
      join(env.USERPROFILE, ".codex")

  path = join(home, "auth.json")

  if path missing:
    return MissingCredentials

  json = strict-but-forward-compatible JSON parse

  token = json.tokens.access_token
  account_id = json.tokens.account_id
  last_refresh = json.last_refresh

  if token empty:
    return MissingCredentials

  return CredentialSnapshot(
    access_token = token,
    account_id = account_id,
    last_refresh = last_refresh
  )
```

---

## 4.3 Token freshness

CodexBar treats JWT expiry as a scheduling hint, not as locally verified authentication.

Decode the JWT payload without signature verification only to inspect `exp`.

Important: decoding `exp` does **not** establish token authenticity. The server remains authoritative.

Recommended rule:

```pseudo
if JWT exp exists and is a valid integer timestamp:
  if exp <= now + 5 minutes:
    consider native credentials stale
  else:
    consider token usable
else:
  fall back to last_refresh age
```

CodexBar retains an 8-day age fallback for credentials whose expiry cannot be safely extracted.

For this CLI, implement the same broad behavior:

```pseudo
if valid_exp:
  stale = exp <= now + 300 seconds
else:
  stale = last_refresh missing
          OR last_refresh invalid
          OR now - last_refresh >= 8 days
```

When native credentials are stale:

> do not refresh them yourself; use the Codex CLI RPC fallback.

---

## 4.4 Primary usage request

Endpoint:

```text
GET https://chatgpt.com/backend-api/wham/usage
```

Headers:

```http
Authorization: Bearer <access_token>
ChatGPT-Account-Id: <account_id>
User-Agent: codex-cli
Accept: application/json
```

`ChatGPT-Account-Id` should be omitted only when unavailable.

Representative response:

```json
{
  "plan_type": "pro",
  "rate_limit": {
    "primary_window": {
      "used_percent": 15,
      "reset_at": 1735401600,
      "limit_window_seconds": 18000
    },
    "secondary_window": {
      "used_percent": 5,
      "reset_at": 1735920000,
      "limit_window_seconds": 604800
    }
  },
  "credits": {
    "has_credits": true,
    "unlimited": false,
    "balance": 150.0
  }
}
```

Normalize:

```text
primary_window   -> "5-hour" / session lane
secondary_window -> weekly lane
```

Do not hard-code the display name solely from position. Prefer `limit_window_seconds` when identifying a window:

```text
18000  -> 5 hours
604800 -> 7 days
```

Still preserve unknown durations as generic windows.

### Additional rate limits

Current Codex can return `additional_rate_limits[]` for model-specific allowances.

Do not discard unknown entries.

Normalize each to an extra named window:

```pseudo
for limit in response.additional_rate_limits:
  for window in limit windows:
    append normalized extra window
```

Keep provider IDs/names when available rather than inventing stable names based only on array position.

---

## 4.5 Credits

If present:

```json
{
  "has_credits": true,
  "unlimited": false,
  "balance": 150.0
}
```

Represent separately from percentage quota.

Example:

```json
"credits": {
  "has_credits": true,
  "unlimited": false,
  "balance": 150.0
}
```

Do not infer a percentage from balance unless the API also gives a real credit limit.

CodexBar also probes reset-credit inventory through:

```text
GET https://chatgpt.com/backend-api/wham/rate-limit-reset-credits
```

This is optional for this tool. It is not necessary to answer basic "how much subscription quota is left?"

If implemented, treat it as read-only inventory. Never redeem anything.

---

## 4.6 Error behavior

Recommended classification:

```text
200          parse
401 / 403    AuthExpiredOrInvalid
408 / timeout NetworkTimeout
429          ProviderThrottled
5xx          ProviderUnavailable
other        ProviderHTTPError
JSON failure ProviderSchemaChanged
```

AUTO behavior:

```pseudo
try OAuth:
  if fresh credentials and success:
    return result

  if missing credentials:
    try CLI RPC

  if native credentials stale:
    try CLI RPC

  if 401/403:
    try CLI RPC

  if decode error / 5xx / network outage:
    surface original error
    do not pretend a different account/session is equivalent
```

The fail-closed behavior matters for account correctness.

---

# 5. Codex CLI RPC fallback

## 5.1 Why use it

`codex app-server`:

- owns Codex auth refresh;
- returns structured account information;
- returns structured rate limits;
- avoids parsing the interactive `/status` screen.

Do **not** parse bare Codex TUI output in normal operation.

---

## 5.2 Launch

Equivalent invocation:

```text
codex -s read-only -a never app-server
```

On Windows, launch `codex.exe`/resolved `codex` directly rather than reproducing CodexBar's macOS `/usr/bin/env` wrapper.

Use redirected stdin/stdout/stderr.

Protocol is newline-delimited JSON messages over stdin/stdout.

---

## 5.3 RPC sequence

Initialization:

```json
{"id":1,"method":"initialize","params":{"clientInfo":{"name":"llm-usage","version":"0.1.0"}}}
```

Wait for result with matching ID.

Then send notification:

```json
{"method":"initialized","params":{}}
```

Read account:

```json
{"id":2,"method":"account/read","params":{}}
```

Read rate limits:

```json
{"id":3,"method":"account/rateLimits/read","params":{}}
```

Ignore unrelated notifications that have a `method` but no matching request `id`.

Suggested timeouts based on CodexBar:

```text
initialize: 8 s
normal RPC: 3 s
```

If a request times out:

1. close stdin;
2. terminate the process;
3. after a short grace period, kill it;
4. report timeout.

Never leave orphan app-server processes.

---

## 5.4 Relevant RPC response fields

Account response conceptually contains:

```text
account.type
account.email
account.planType
requiresOpenaiAuth
```

Rate-limit response:

```text
rateLimits.primary.usedPercent
rateLimits.primary.windowDurationMins
rateLimits.primary.resetsAt

rateLimits.secondary.usedPercent
rateLimits.secondary.windowDurationMins
rateLimits.secondary.resetsAt

rateLimits.credits
rateLimits.planType
```

Current Codex can also expose:

```text
rateLimitsByLimitId
rate_limits_by_limit_id
```

Accept both camelCase and snake_case variants.

Treat this map as model-/limit-specific extra windows.

---

# 6. Cursor

## 6.1 Recommended Windows source order

```text
AUTO
  1. Cursor desktop local access token from state.vscdb
  2. configured manual Cursor cookie header
  3. fail with guidance
```

Do not begin with browser-cookie extraction.

On Windows, Chromium cookie stores are encrypted and browser-specific. That adds significant security and maintenance surface for little benefit when Cursor already exposes an access token in its application state.

CodexBar currently compiles its direct Cursor-app auth loader only for macOS, but the mechanism itself is portable: read the Cursor access token, validate its JWT metadata, and convert it into Cursor's web-session cookie.

The Windows Cursor state database path is:

```text
%APPDATA%\Cursor\User\globalStorage\state.vscdb
```

---

## 6.2 Read Cursor's local access token

Database:

```text
%APPDATA%\Cursor\User\globalStorage\state.vscdb
```

SQLite table/key:

```sql
SELECT value
FROM ItemTable
WHERE key = 'cursorAuth/accessToken'
LIMIT 1;
```

Open read-only.

### WAL correctness

Cursor may have:

```text
state.vscdb
state.vscdb-wal
state.vscdb-shm
```

Do not copy or open only the main database while Cursor is running and then assume the result is current.

Recommended behavior:

```pseudo
open SQLite URI with mode=ro

if WAL/shm sidecars exist:
  use normal read-only SQLite connection so WAL is visible

if main DB says WAL mode but sidecars are absent:
  a read-only/immutable fallback may be used
```

Never execute schema changes, checkpoints, VACUUM, journal-mode changes, or writes.

Set a small busy timeout, e.g. 250 ms.

---

## 6.3 Decode the SQLite value carefully

CodexBar handles a subtle case where token BLOBs can be BOM-less ASCII UTF-16LE.

Recommended order:

```pseudo
if SQLite value is TEXT:
  return text

if SQLite value is BLOB:
  if byte_length even
     and every odd byte == 0
     and every even byte is nonzero ASCII:
       try UTF-16LE first

  try UTF-8
  then UTF-16LE

otherwise:
  no token
```

Do not trim or mutate a nonempty token beyond surrounding storage decoding.

A malformed but nonempty token should be classified differently from "token missing"; otherwise fallback logic may accidentally use stale credentials from another account.

---

# 7. Cursor token -> session cookie

Cursor's local access token is a JWT.

Decode its payload.

Required claims:

```text
sub
exp
```

Useful claim:

```text
email
```

### User ID

Cursor's JWT `sub` may contain components separated by `|`.

CodexBar derives:

```pseudo
user_id = last nonempty segment of sub.split("|")
```

Validate that `user_id` contains only:

```text
A-Z a-z 0-9 . _ -
```

### Expiration

Require:

```text
exp > now + 60 seconds
```

If not, consider the app token unusable.

Do not refresh it. Cursor owns refresh.

### Construct web session cookie

CodexBar derives:

```text
WorkosCursorSessionToken=<user_id>%3A%3A<access_token>
```

That is the URL-encoded equivalent of:

```text
<user_id>::<access_token>
```

Example header:

```http
Cookie: WorkosCursorSessionToken=abc123%3A%3AeyJ...
```

This is the key Windows simplification: no Chrome/Edge cookie decryption is necessary for the normal path.

---

# 8. Cursor usage API

## 8.1 Requests

With one resolved cookie header, fetch these in parallel:

### Required

```text
GET https://cursor.com/api/usage-summary
```

Headers:

```http
Accept: application/json
Cookie: <resolved-cookie-header>
```

### Optional identity enrichment

```text
GET https://cursor.com/api/auth/me
```

Same cookie.

### Optional Grok Bot / Sand quota

```text
POST https://cursor.com/api/dashboard/get-sand-usage-status
```

Headers:

```http
Accept: application/json
Content-Type: application/json
Origin: https://cursor.com
Cookie: <resolved-cookie-header>
```

Body:

```json
{}
```

CodexBar caps this optional request at about 5 seconds. Its failure must not invalidate the main Cursor usage result.

### Legacy request-plan enrichment

After `/api/auth/me` gives `sub`:

```text
GET https://cursor.com/api/usage?user=<sub>
```

Best-effort only.

Not every plan uses this endpoint.

---

# 9. Cursor usage-summary schema and normalization

Useful fields:

```text
billingCycleStart
billingCycleEnd
membershipType

individualUsage.plan.used
individualUsage.plan.limit
individualUsage.plan.autoPercentUsed
individualUsage.plan.apiPercentUsed
individualUsage.plan.totalPercentUsed

individualUsage.onDemand.used
individualUsage.onDemand.limit

individualUsage.overall.used
individualUsage.overall.limit

teamUsage.onDemand.used
teamUsage.onDemand.limit

teamUsage.pooled.used
teamUsage.pooled.limit
```

Currency-like usage fields here are expressed in cents.

Convert to USD:

```text
usd = cents / 100.0
```

## 9.1 Headline Cursor usage percentage

Use this precedence:

```pseudo
if individualUsage.plan.totalPercentUsed exists:
  total = that

else if autoPercentUsed and apiPercentUsed both exist:
  total = (auto + api) / 2

else if apiPercentUsed exists:
  total = api

else if autoPercentUsed exists:
  total = auto

else if individualUsage.plan.limit > 0:
  total = 100 * plan.used / plan.limit

else if individualUsage.overall.limit > 0:
  total = 100 * overall.used / overall.limit

else if teamUsage.pooled.limit > 0:
  total = 100 * pooled.used / pooled.limit

else:
  usage unknown
```

Important:

> Cursor percentage fields are already percentage units.

For example:

```text
0.36 means 0.36%, not 36%.
```

Do not multiply Cursor's percent fields by 100.

Clamp valid display values to `[0, 100]`.

---

## 9.2 Cursor secondary lanes

For modern token-/spend-based plans:

```text
primary   = total plan usage
secondary = autoPercentUsed
tertiary  = apiPercentUsed
```

Possible labels:

```text
Total
Cursor
Third Party
```

or keep more literal implementation-oriented names:

```text
Total
Auto / Composer
API / named models
```

Choose one stable public vocabulary and document it.

---

## 9.3 Legacy request-based Cursor plans

From:

```text
GET /api/usage?user=<id>
```

Relevant fields under `"gpt-4"`:

```text
numRequests
numRequestsTotal
maxRequestUsage
```

Derive:

```pseudo
requests_used = numRequestsTotal ?? numRequests
requests_limit = maxRequestUsage
```

If `requests_limit > 0`, this is a usable legacy request quota.

Then:

```text
used_percent = 100 * requests_used / requests_limit
```

Prefer this request quota as the primary display and hide modern auto/API percentage lanes to avoid mixing incompatible quota systems.

---

## 9.4 Billing reset

Parse:

```text
billingCycleStart
billingCycleEnd
```

as ISO-8601, accepting timestamps with or without fractional seconds.

Use:

```text
resets_at = billingCycleEnd
```

For the normalized window length:

```text
window_seconds = billingCycleEnd - billingCycleStart
```

when both are valid and ordered.

---

## 9.5 On-demand budget

Personal:

```text
individualUsage.onDemand.used
individualUsage.onDemand.limit
```

Team:

```text
teamUsage.onDemand.used
teamUsage.onDemand.limit
```

CodexBar resolves the budget approximately as:

```pseudo
if personal limit > 0:
  use personal on-demand usage and cap
else if team limit > 0:
  use shared team usage and cap
else:
  preserve personal values if any
```

Keep this separate from included-plan quota.

Example normalized extension:

```json
"spend": {
  "used_usd": 7.38,
  "limit_usd": 100.00,
  "period": "billing-cycle"
}
```

---

# 10. Cursor Grok Bot quota

Endpoint:

```text
POST /api/dashboard/get-sand-usage-status
```

Observed semantics:

```text
usagePercent
nextResetTimestampUtc
```

Represent as an extra quota window:

```text
label       = Grok Bot
used        = usagePercent
resets_at   = nextResetTimestampUtc
window      = weekly
```

Only publish it when the response describes a real nonzero allowance.

Failure is nonfatal.

---

# 11. Cursor manual cookie fallback

Configuration may accept a literal `Cookie:` header copied from an authenticated request to `cursor.com`.

Example:

```toml
[cursor]
cookie = "WorkosCursorSessionToken=..."
```

Security requirements:

- config file should be readable only by the current user where practical;
- never print cookie values;
- `--verbose` must redact them;
- JSON output must not include raw credentials.

Manual means manual:

> If the user explicitly configures a cookie, do not silently replace it with a different account's app token after an authentication failure.

This avoids cross-account surprises.

---

# 12. Antigravity

## 12.1 Preferred Windows strategy

For this CLI, prefer the official `agy` CLI path.

Antigravity's local service exposes richer quota information than the remote OAuth path and current IDE local payloads.

Recommended AUTO:

```text
1. find/reuse an already-running agy belonging to current user
2. otherwise launch agy in a pseudo-console
3. discover its localhost listening port(s)
4. probe RetrieveUserQuotaSummary
5. fallback GetUserStatus
6. fallback GetCommandModelConfigs
7. terminate only the agy process launched by this invocation
```

Do not scrape `agy` terminal output.

The terminal process exists only to keep its internal local service alive.

---

# 13. Locating and launching agy on Windows

Discovery:

```pseudo
if LLM_USAGE_ANTIGRAVITY_CLI configured:
  use exact configured path

else:
  resolve "agy.exe" from PATH

else:
  run Windows path lookup equivalent to `where.exe agy`

else:
  return NotInstalled
```

Google's Windows installer normally adds `agy` to PATH.

First-run authentication should remain provider-owned.

If `agy` is signed out:

```text
Tell user to run `agy` interactively once and sign in.
```

Do not automate Google login inside the usage tool.

## 13.1 Windows process launching & pseudo-console differences

CodexBar launches `agy` under a POSIX PTY (`openpty`/`forkpty`) on macOS/Linux because its local server is tied to an interactive process, and detached Unix PTYs run with zero UI footprint.

On Windows 11:
- `agy.exe` is compiled as a Console Subsystem binary (`IMAGE_SUBSYSTEM_WINDOWS_CUI`).
- Spawning `agy.exe` with `stdin=subprocess.PIPE` stalls `agy.exe` waiting on stream input, preventing the Language Server from binding to ports.
- Spawning `agy.exe` without `creationflags=subprocess.CREATE_NO_WINDOW` (`0x08000000`) causes Windows to attach or allocate a console context, which may briefly flicker a console host window or appear visibly in Task Manager.
- Instead, launching `agy.exe` with:
  ```python
  stdin=subprocess.DEVNULL,
  stdout=subprocess.DEVNULL,
  stderr=subprocess.DEVNULL,
  creationflags=subprocess.CREATE_NO_WINDOW
  ```
  allows `agy.exe` to start cleanly and non-interactively in the background, bind to its loopback ports within ~200ms, and run with zero console window footprint.

### 13.2 Scope of process discovery (`agy`, `antigravity`, `language_server`)

CodexBar on macOS/Linux inspects processes matching `language_server`, `antigravity`, and `agy`.
On Windows:
- Standalone CLI: `agy.exe`
- Antigravity Desktop App / IDE extension: runs `language_server.exe` (located at `%LOCALAPPDATA%\Programs\antigravity\resources\bin\language_server.exe`).
- Process inspection must scan across all three names (`agy`, `antigravity`, and `language_server`) to reuse existing listening ports without unnecessarily spawning duplicate background instances.

---

# 14. Antigravity port discovery on Windows

CodexBar uses PID-scoped listener discovery on macOS/Linux.

Windows equivalent should be implemented with the IP Helper API, preferably:

```text
GetExtendedTcpTable
```

using owner-PID TCP table classes.

Algorithm:

```pseudo
function listening_ports_for_pid(pid):
  rows4 = GetExtendedTcpTable(AF_INET, owner_pid_all)
  rows6 = GetExtendedTcpTable(AF_INET6, owner_pid_all)

  return unique local ports where:
    owning_pid == pid
    TCP state == LISTEN
```

If `agy` starts a service in a child process in the tested Windows build, extend this to the owned descendant process tree.

Do not probe every listening port on the machine.

Restrict discovery to the target process/owned descendants.

As a diagnostic-only fallback, PowerShell can query:

```powershell
Get-NetTCPConnection -State Listen |
  Where-Object OwningProcess -eq $pid
```

but the production executable should not depend on PowerShell if a native API is practical.

---

# 15. Antigravity localhost protocol

Try each candidate listening port.

The preferred endpoint:

```text
POST https://127.0.0.1:<port>/exa.language_server_pb.LanguageServerService/RetrieveUserQuotaSummary
```

Headers:

```http
Content-Type: application/json
Content-Length: <bytes>
Connect-Protocol-Version: 1
```

For the `agy` CLI source:

```text
DO NOT send X-Codeium-Csrf-Token
```

Body:

```json
{
  "forceRefresh": true
}
```

Only accept HTTP 200 as a successful payload.

---

# 16. Localhost TLS safety

Antigravity's local HTTPS server can use a self-signed certificate.

A client may need to relax certificate validation.

If doing so:

> the insecure trust exception must be impossible to use for non-loopback traffic.

Recommended design:

```text
normal_http_client
  -> normal certificate verification
  -> all remote provider APIs

antigravity_loopback_client
  -> may accept Antigravity self-signed certificate
  -> URL builder hard-coded to scheme=https, host=127.0.0.1
  -> rejects redirects
  -> cannot accept arbitrary hostnames
```

Never use a process-global "accept invalid certificates" option.

Never follow a redirect from the loopback client to a non-loopback host.

This is a security boundary, not just a networking detail.

---

# 17. Antigravity quota-summary parsing

Preferred response structure conceptually contains:

```text
response.groups[]
  .displayName
  .buckets[]
    .bucketId
    .displayName
    .remaining.remainingFraction
    .description
```

CodexBar normalizes these into two main families:

```text
Gemini
Claude/GPT
```

and two common cadences:

```text
5-hour
weekly
```

Expected user-facing windows:

```text
Gemini 5-hour
Gemini weekly
Claude/GPT 5-hour
Claude/GPT weekly
```

### Remaining -> used

The endpoint reports remaining quota:

```pseudo
remaining_percent = clamp(remainingFraction * 100, 0, 100)
used_percent = 100 - remaining_percent
```

### Cadence inference

Recognize 5-hour/session aliases in `bucketId` or display name:

```text
session
5h
5-hour
five hour
five-hour
```

Recognize:

```text
weekly
```

Map:

```text
session -> 300 minutes
weekly  -> 10080 minutes
```

Do not invent a duration for unrecognized bucket names.

### Reset description

The preferred quota summary often carries reset prose in:

```text
bucket.description
```

Preserve it as auxiliary text.

If the payload also supplies a machine-readable reset timestamp in a future version, prefer the machine-readable timestamp.

---

# 18. Antigravity representative/compact usage

If the CLI needs one compact number per model family, choose the most constrained known bucket.

Equivalent rule:

```pseudo
for family in [Gemini, Claude/GPT]:
  known = windows where usage_known == true
  representative = window with greatest used_percent
```

This means the most depleted applicable window drives the compact summary.

Do not average the 5-hour and weekly quotas.

Always retain the individual windows in JSON.

---

# 19. Antigravity fallback endpoints

If `RetrieveUserQuotaSummary` fails or returns no usable bucket:

### Fallback 1

```text
POST https://127.0.0.1:<port>/exa.language_server_pb.LanguageServerService/GetUserStatus
```

Body:

```json
{
  "metadata": {
    "ideName": "antigravity",
    "extensionName": "antigravity",
    "ideVersion": "unknown",
    "locale": "en"
  }
}
```

Parse:

```text
userStatus.email
userStatus.userTier
userStatus.planStatus.planInfo
userStatus.cascadeModelConfigData.clientModelConfigs[]
```

Model quota:

```text
quotaInfo.remainingFraction
quotaInfo.resetTime
```

Prefer actual user-tier name over generic plan-info labels when both exist.

### Fallback 2

```text
POST https://127.0.0.1:<port>/exa.language_server_pb.LanguageServerService/GetCommandModelConfigs
```

Same metadata body.

Parse model config quota fields in the same way.

### Legacy model-family aggregation

For legacy model-level rows:

- Gemini Pro / Flash text models -> Gemini pool
- Claude text models + GPT/GPT-OSS text models -> Claude/GPT pool
- ignore image/autocomplete/lite rows as representative summary drivers
- for each pool choose the lowest remaining quota / highest used percentage
- preserve reset metadata from the selected row

Unknown model IDs should be retained as extras when they contain real quota data.

---

# 20. Antigravity readiness polling

A newly launched `agy` may bind a TCP port before its quota API is ready.

Therefore:

```pseudo
deadline = now + startup_timeout

repeat until deadline:
  ports = listening_ports_for_owned_agy()

  for port in ports:
    try RetrieveUserQuotaSummary
    if parseable usable quota:
      success

    try GetUserStatus
    if parseable quota:
      success

    try GetCommandModelConfigs
    if parseable quota:
      success

  sleep short_backoff
```

Suggested backoff:

```text
200 ms -> 300 ms -> 500 ms -> 750 ms -> 1 s
```

Cap total startup/readiness time, e.g. 8-12 seconds.

Readiness is defined by **parseable API data**, not merely "port is listening."

---

# 21. Optional Antigravity remote OAuth path

This should be v2 unless there is a strong need for background quota when `agy` is unavailable.

CodexBar's remote path uses:

```text
POST https://cloudcode-pa.googleapis.com/v1internal:loadCodeAssist
POST https://cloudcode-pa.googleapis.com/v1internal:onboardUser
POST https://cloudcode-pa.googleapis.com/v1internal:fetchAvailableModels
POST https://cloudcode-pa.googleapis.com/v1internal:retrieveUserQuota
```

Auth:

```http
Authorization: Bearer <Google access token>
Content-Type: application/json
User-Agent: antigravity
```

`loadCodeAssist` body:

```json
{
  "metadata": {
    "ideType": "ANTIGRAVITY",
    "platform": "PLATFORM_UNSPECIFIED",
    "pluginType": "GEMINI"
  }
}
```

The remote API can expose less complete quota information than `agy`.

Important observed behavior:

```text
fetchAvailableModels may show every quota as effectively 100% remaining.
```

CodexBar does not blindly trust that as real usage. If all model quotas are near 100%, it attempts `retrieveUserQuota` to verify actual fractions. If verification is unavailable, it may treat limits as unavailable rather than reporting fake all-clear usage.

If implementing remote OAuth, preserve that conservative behavior.

OAuth refresh is a separate credential-ownership problem and should not be mixed into the initial `agy` implementation.

---

# 22. Provider state machines

## 22.1 Codex

```text
START
  |
  v
find auth.json
  |
  +-- missing ------------------------------+
  |                                         |
  v                                         v
read token                               CLI RPC
  |
  v
fresh?
  |
  +-- no ----------------------------------> CLI RPC
  |
 yes
  |
  v
GET wham/usage
  |
  +-- 401/403 ------------------------------> CLI RPC
  |
  +-- schema/network/server error ----------> ERROR
  |
 success
  |
  v
NORMALIZE
```

## 22.2 Cursor

```text
START
  |
  v
read state.vscdb
  |
  +-- token absent/unusable ---> manual cookie configured?
  |                                  |
  |                                  +-- no -> AUTH ERROR
  |                                  |
  |                                  yes
  |                                   |
  +-----------------------------------+
                                      v
                                resolved cookie
                                      |
                                      v
                     +----------------+----------------+
                     |                |                |
                     v                v                v
                usage-summary      auth/me        sand status
                  required         optional         optional
                     |
                     v
             optional legacy usage
                     |
                     v
                  NORMALIZE
```

## 22.3 Antigravity

```text
START
  |
  v
locate agy
  |
  +-- missing -> NOT INSTALLED
  |
  v
reuse compatible running agy?
  |
  +-- no -> launch owned agy in ConPTY
  |
  v
discover PID-scoped listening ports
  |
  v
poll endpoints until parseable
  |
  +-- quota summary -> NORMALIZE
  |
  +-- GetUserStatus -> NORMALIZE LEGACY
  |
  +-- command configs -> NORMALIZE LEGACY
  |
  +-- timeout -> actionable error
```

---

# 23. Caching and freshness

This tool is small enough that aggressive caching is unnecessary.

Recommended:

```text
in-process result cache: 15-30 seconds
disk cache: optional
```

If a disk cache is added, it must carry:

```text
provider
credential/account fingerprint
source
fetched_at
normalized result
```

Never cache raw OAuth tokens or cookies in the result cache.

A stale result may be shown only if explicitly labeled:

```text
STALE: last successful read 12m ago
```

Do not replace a failed live fetch with stale data without telling the caller.

JSON:

```json
{
  "stale": true,
  "fetched_at": "...",
  "live_error": "..."
}
```

---

# 24. Account identity and race safety

A usage monitor can return the wrong account if credentials change while requests are in flight.

For every provider:

1. resolve credentials/session once;
2. compute a nonreversible fingerprint;
3. use that same credential snapshot for every request in the refresh;
4. before publishing, optionally confirm the active credential source has not switched;
5. discard/retry if account ownership changed.

Do not include bearer tokens in fingerprints directly.

Example:

```text
fingerprint = SHA-256(provider || stable_account_id || credential_material_hash)
```

Never print the hash unless useful for debug, and never print source credential material.

---

# 25. Secret handling

Minimum requirements:

- redact `Authorization` headers;
- redact cookies;
- redact refresh tokens;
- redact access tokens;
- redact raw JWTs;
- do not include secrets in error strings;
- do not place credentials into command arguments when avoidable;
- do not persist provider-owned credentials in this tool's config;
- manual cookie configuration is an explicit exception and should be permission-protected.

Verbose logs may show:

```text
Cursor token source: state.vscdb
Cursor token expiry: 2026-09-06T02:00:00Z
Cursor account: user@example.com
```

They must not show the token.

For Antigravity localhost HTTPS, disabled certificate validation must be scoped to loopback only.

---

# 26. Suggested Rust implementation

Rust is a strong fit for a Windows-only/single-binary CLI, but the algorithms are language-independent.

Suggested layout:

```text
src/
  main.rs
  cli.rs
  config.rs
  model.rs
  format.rs
  cache.rs
  redact.rs

  providers/
    mod.rs
    codex/
      mod.rs
      auth.rs
      oauth.rs
      rpc.rs
      parse.rs
    cursor/
      mod.rs
      app_auth.rs
      api.rs
      parse.rs
    antigravity/
      mod.rs
      agy.rs
      localhost.rs
      parse.rs

  windows/
    paths.rs
    process.rs
    tcp_table.rs
    conpty.rs
```

Potential crates:

```text
clap
serde / serde_json
tokio
reqwest
thiserror
rusqlite
base64
sha2
time or chrono
windows
```

For pseudo-terminal support either:

- implement ConPTY through `windows`; or
- use a well-maintained portable PTY crate.

For SQLite, `rusqlite` with bundled SQLite can reduce external dependencies.

---

# 27. Provider trait

Example conceptual interface:

```rust
#[async_trait]
trait UsageProvider {
  async fn fetch(&self, ctx: &FetchContext) -> Result<ProviderUsage>;
  async fn doctor(&self, ctx: &FetchContext) -> DoctorReport;
}
```

Keep provider-specific auth opaque:

```rust
struct ProviderUsage {
  provider: ProviderId,
  account: Option<AccountIdentity>,
  source: SourceLabel,
  windows: Vec<UsageWindow>,
  credits: Option<Credits>,
  spend: Option<Spend>,
  fetched_at: OffsetDateTime,
  warnings: Vec<String>,
}
```

Do not leak provider transport structures into output formatting.

---

# 28. Human-readable output

Example:

```text
Codex  Pro  user@example.com
  5-hour      15% used  85% left  resets in 2h 14m
  Weekly       5% used  95% left  resets Sep 10 8:00 PM
  Credits      $150.00

Cursor  Pro  user@example.com
  Total        42% used  58% left  resets Sep 28
  Cursor       31% used
  Third Party  53% used
  Grok Bot     18% used  resets Sep 9
  On-demand    $7.38 / $100.00

Antigravity  Google AI Ultra  user@example.com
  Gemini 5h       21% used  79% left
  Gemini weekly   46% used  54% left
  Claude/GPT 5h   12% used  88% left
  Claude/GPT wk   34% used  66% left
```

When unknown:

```text
Antigravity
  Limits not available from the current authenticated source.
```

Do not print `0% used` as a substitute.

---

# 29. JSON compatibility contract

Treat JSON output as public API from the first release.

Recommended rules:

- snake_case field names;
- additive evolution;
- never reinterpret existing units;
- percentages always `0..100`, never `0..1`;
- currency always decimal major units with `currency`;
- UTC RFC3339 timestamps;
- unknown values are `null`;
- source labels are stable identifiers, not prose.

Example sources:

```text
codex_oauth
codex_rpc
cursor_app_token
cursor_manual_cookie
antigravity_agy
antigravity_oauth
```

---

# 30. Doctor command

`usage doctor` should check local prerequisites without exposing secrets.

Example:

```text
Codex
  [ok] codex found: C:\...\codex.exe
  [ok] auth file found
  [ok] OAuth access token present
  [ok] token fresh enough for direct usage fetch

Cursor
  [ok] state.vscdb found
  [ok] cursorAuth/accessToken found
  [ok] token expires in 3h 14m
  [ok] cursor.com session validation succeeded

Antigravity
  [ok] agy found
  [ok] agy authenticated
  [ok] local quota service reachable
  [ok] RetrieveUserQuotaSummary supported
```

Failure example:

```text
Antigravity
  [ok] agy found
  [fail] agy is not signed in
         Run `agy` once in a terminal and complete Google sign-in.
```

---

# 31. Testing strategy

## 31.1 No live credentials in unit tests

Use fixtures for:

- Codex `auth.json`;
- Codex `wham/usage`;
- Codex RPC lines;
- Cursor SQLite databases;
- Cursor usage-summary responses;
- Cursor legacy request-plan responses;
- Antigravity quota-summary payloads;
- Antigravity legacy user-status payloads.

Never commit real tokens or cookies.

---

## 31.2 Codex tests

Required cases:

```text
fresh JWT -> OAuth called
JWT exp within 5m -> RPC fallback
opaque JWT + recent last_refresh -> OAuth
opaque JWT + stale last_refresh -> RPC
401 -> RPC
rate_limit.primary only
primary + secondary
additional_rate_limits preserved
unknown plan string does not crash parser
RPC camelCase fields
RPC snake_case limit map
RPC ignores notifications
RPC timeout kills child
```

Forward-compatible plan parsing is important. Prefer a string plan field over a closed enum unless unknown enum values are explicitly preserved.

---

## 31.3 Cursor tests

Required:

```text
Windows DB path resolution
TEXT token
UTF-8 BLOB token
ASCII UTF-16LE BLOB token
malformed nonempty token != missing token
JWT subject -> user ID
invalid user-ID characters rejected
exp <= 60s rejected
cookie is exactly userID%3A%3Atoken
usage-summary 401 -> auth error
fractional 0.36 percentage remains 0.36%
totalPercentUsed precedence
auto/api averaging
plan used/limit fallback
enterprise overall fallback
team pooled fallback
legacy request-plan override
billing timestamps with fractional seconds
billing timestamps without fractional seconds
sand failure nonfatal
```

Add an integration test against a temporary SQLite database with `ItemTable`.

---

## 31.4 Antigravity tests

Required:

```text
PID-scoped port discovery
only loopback URLs allowed
self-signed TLS exception cannot escape loopback
RetrieveUserQuotaSummary preferred
forceRefresh=true
CLI source sends no CSRF header
Connect-Protocol-Version=1
summary remaining -> used conversion
session alias recognition
weekly recognition
unknown bucket retained
empty/unusable summary falls back
GetUserStatus parsing
GetCommandModelConfigs parsing
cold agy readiness retries
owned agy is terminated
pre-existing agy is never killed
timeout does not leave child
```

A security test should explicitly try to redirect the loopback HTTP client to an external URL and verify rejection.

---

# 32. Live acceptance tests on Windows

Before calling the implementation complete, validate on a real Windows 11 machine with each subscription.

## Codex

1. `codex` is signed in.
2. Compare tool output against Codex's own current usage/status display.
3. Use enough quota to make both 5-hour and weekly values nontrivial.
4. Confirm reset timestamps.
5. Expire/re-authenticate session and confirm RPC recovery works.
6. Confirm `auth.json` content hash is unchanged by the tool.

## Cursor

1. Cursor desktop is signed in.
2. Confirm `state.vscdb` contains `cursorAuth/accessToken`.
3. Confirm derived cookie authenticates `/api/usage-summary`.
4. Compare Total / Cursor / Third Party values against Cursor's dashboard.
5. Test while Cursor is running so WAL behavior is exercised.
6. Test after Cursor is closed.
7. Test token expiry/sign-out.
8. If available, test Team/Enterprise and legacy request-based shapes.

**Important:** upstream CodexBar's local Cursor token loader is not currently a Windows implementation. The Windows adaptation must be validated against a real current Cursor build before it is considered stable.

## Antigravity

1. Install and sign into `agy`.
2. Verify tool can launch it under ConPTY.
3. Verify PID-scoped port discovery.
4. Compare four quota windows against Antigravity's model quota UI.
5. Test a cold launch.
6. Test reuse of an already-running `agy`.
7. Confirm the tool never kills a pre-existing user-owned `agy`.
8. Confirm no terminal-output parsing is used.

---

# 33. Failure policy

A quota monitor should prefer "unknown" over "plausible but wrong."

Examples:

```text
GOOD:
  Cursor usage unavailable: session expired.

BAD:
  Cursor: 0% used
```

```text
GOOD:
  Antigravity OAuth authenticated, but numeric limits are unavailable.

BAD:
  Antigravity: 100% left
```

```text
GOOD:
  Codex usage schema changed; raw response omitted for security.

BAD:
  Weekly: 0% used
```

The tool should return distinct exit codes if useful:

```text
0  success
2  partial success (some providers failed)
3  authentication required
4  provider unavailable
5  local dependency missing
6  schema/protocol incompatibility
```

For `usage all`, prefer printing successful providers and returning partial-success rather than failing the entire command.

---

# 34. Recommended implementation stages

## Stage 1: normalized core + Codex

- CLI shell
- normalized JSON schema
- Codex auth discovery
- `wham/usage`
- Codex RPC fallback
- redaction
- tests

This establishes the most conventional provider flow.

## Stage 2: Cursor

- Windows `state.vscdb` read-only access
- JWT/session-cookie derivation
- usage-summary
- auth/me
- legacy request-plan enrichment
- Sand/Grok quota
- live Windows validation

No browser-cookie import yet.

## Stage 3: Antigravity

- `agy` discovery
- ConPTY lifecycle
- Windows PID -> port discovery
- self-signed loopback HTTP client
- quota-summary parser
- legacy local endpoint fallback
- lifecycle and security tests

## Stage 4: hardening

- `doctor`
- stale-result policy
- short cache
- account-race protection
- structured verbose diagnostics
- installer/release packaging

## Stage 5: optional only

- Cursor browser-cookie fallback
- Antigravity remote OAuth
- multi-account profiles

Do not let Stage 5 delay a reliable three-provider v1.

---

# 35. Important implementation judgments

## 35.1 Do not port CodexBar wholesale

CodexBar solves a much broader macOS menu-bar problem.

The useful core for this project is much smaller:

```text
Codex:
  auth.json -> wham/usage
  codex app-server -> structured fallback

Cursor:
  state.vscdb -> access token -> Workos cookie -> dashboard APIs

Antigravity:
  agy -> localhost port -> quota summary
```

This is the essence.

## 35.2 Prefer structured protocols over scraping

Priority:

```text
structured provider API
> local structured RPC/API
> provider-owned local credential derivation
> manual cookie
>>>>>>>> terminal/DOM scraping
```

The current CodexBar implementation has already migrated important paths away from fragile rendered-text parsing.

## 35.3 Provider-owned refresh stays provider-owned

- Codex token stale -> let Codex CLI recover it.
- Cursor token stale -> let Cursor refresh it.
- `agy` signed out -> let user authenticate through `agy`.

A usage monitor should not become a second authentication client unless necessary.

## 35.4 "Current usage" is not one number

Expose windows rather than collapsing them.

Codex can have session + weekly + model-specific limits.

Cursor can have included-plan + component lanes + legacy request cap + Grok allowance + on-demand budget.

Antigravity can have Gemini and Claude/GPT, each with session and weekly limits.

A single averaged "usage score" would lose the operational information the user actually needs.

---

# 36. Upstream CodexBar source map

All links below are pinned to the revision analyzed.

## Codex

Provider documentation:

https://github.com/steipete/CodexBar/blob/211781be79d37fd942bc4ee623abd6d5c8baeffd/docs/codex.md

OAuth design and usage schema:

https://github.com/steipete/CodexBar/blob/211781be79d37fd942bc4ee623abd6d5c8baeffd/docs/codex-oauth.md

OAuth fetcher:

https://github.com/steipete/CodexBar/blob/211781be79d37fd942bc4ee623abd6d5c8baeffd/Sources/CodexBarCore/Providers/Codex/CodexOAuth/CodexOAuthUsageFetcher.swift

CLI RPC:

https://github.com/steipete/CodexBar/blob/211781be79d37fd942bc4ee623abd6d5c8baeffd/Sources/CodexBarCore/UsageFetcher.swift

## Cursor

Provider documentation:

https://github.com/steipete/CodexBar/blob/211781be79d37fd942bc4ee623abd6d5c8baeffd/docs/cursor.md

Status/API parser:

https://github.com/steipete/CodexBar/blob/211781be79d37fd942bc4ee623abd6d5c8baeffd/Sources/CodexBarCore/Providers/Cursor/CursorStatusProbe.swift

Cursor app-token/session derivation:

https://github.com/steipete/CodexBar/blob/211781be79d37fd942bc4ee623abd6d5c8baeffd/Sources/CodexBarCore/Providers/Cursor/CursorAppAuth.swift

Grok/Sand quota:

https://github.com/steipete/CodexBar/blob/211781be79d37fd942bc4ee623abd6d5c8baeffd/Sources/CodexBarCore/Providers/Cursor/CursorSandUsage.swift

## Antigravity

Provider documentation:

https://github.com/steipete/CodexBar/blob/211781be79d37fd942bc4ee623abd6d5c8baeffd/docs/antigravity.md

Local status/quota protocol:

https://github.com/steipete/CodexBar/blob/211781be79d37fd942bc4ee623abd6d5c8baeffd/Sources/CodexBarCore/Providers/Antigravity/AntigravityStatusProbe.swift

Localhost TLS behavior:

https://github.com/steipete/CodexBar/blob/211781be79d37fd942bc4ee623abd6d5c8baeffd/Sources/CodexBarCore/Providers/Antigravity/AntigravityLocalhostSession.swift

CLI session lifecycle:

https://github.com/steipete/CodexBar/blob/211781be79d37fd942bc4ee623abd6d5c8baeffd/Sources/CodexBarCore/Providers/Antigravity/AntigravityCLISession.swift

Remote OAuth fallback:

https://github.com/steipete/CodexBar/blob/211781be79d37fd942bc4ee623abd6d5c8baeffd/Sources/CodexBarCore/Providers/Antigravity/AntigravityRemoteUsageFetcher.swift

OAuth credentials:

https://github.com/steipete/CodexBar/blob/211781be79d37fd942bc4ee623abd6d5c8baeffd/Sources/CodexBarCore/Providers/Antigravity/AntigravityOAuthCredentialsStore.swift

## License

https://github.com/steipete/CodexBar/blob/211781be79d37fd942bc4ee623abd6d5c8baeffd/LICENSE

CodexBar is MIT licensed. If implementation agents directly copy substantial source, preserve the required license/copyright notice.

---

# 37. External Windows-specific confirmations

These details are not merely inferred from macOS paths:

- Current Cursor Windows support discussions identify its state database at:
  `%APPDATA%\Cursor\User\globalStorage\state.vscdb`.
- Google's current Antigravity CLI codelab provides native PowerShell/CMD installation paths for Windows and uses the `agy` command.

These should still be covered by live integration tests because both products update frequently.

---

# 38. Definition of done

The project is ready for daily use when all of the following hold:

- `usage --json` returns a stable schema.
- Codex reports current session/weekly limits without browser scraping.
- Codex stale auth recovers through the provider-owned CLI path.
- Cursor reports current usage from the installed Windows Cursor session without browser-cookie extraction.
- Cursor correctly distinguishes modern and legacy request-based plans.
- Antigravity reports its real 5-hour and weekly model-family quotas through `agy`.
- Antigravity self-signed TLS handling cannot escape loopback.
- Existing provider credential files are never modified by the monitor.
- Secrets never appear in stdout/stderr or verbose logs.
- A failure from one provider does not erase successful results from the others.
- "Unknown" is preserved as unknown rather than rendered as zero usage.
- Live values have been cross-checked against each provider's own UI on Windows.

The resulting utility should remain much smaller than CodexBar because it is solving a narrower problem: **three providers, structured quota retrieval, one CLI, Windows only.**
