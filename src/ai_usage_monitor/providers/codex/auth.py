"""Codex credential discovery, parsing and freshness evaluation."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import time
from ai_usage_monitor.windows.paths import get_codex_auth_path


@dataclass(frozen=True)
class CodexCredentials:
  access_token: str
  account_id: str | None
  last_refresh: str | None
  email: str | None = None


def decode_jwt_exp(token: str) -> int | None:
  """Extract expiration timestamp from a JWT without signature verification."""
  try:
    parts = token.split(".")
    if len(parts) < 2:
      return None
    payload_b64 = parts[1]
    payload_b64 += "=" * (-len(payload_b64) % 4)
    payload_bytes = base64.urlsafe_b64decode(payload_b64)
    payload = json.loads(payload_bytes)
    exp = payload.get("exp")
    if isinstance(exp, (int, float)):
      return int(exp)
  except Exception:
    pass
  return None


def extract_jwt_claim(token: str, claim_name: str) -> str | None:
  """Extract a string claim from a JWT payload."""
  try:
    parts = token.split(".")
    if len(parts) < 2:
      return None
    payload_b64 = parts[1]
    payload_b64 += "=" * (-len(payload_b64) % 4)
    payload_bytes = base64.urlsafe_b64decode(payload_b64)
    payload = json.loads(payload_bytes)
    val = payload.get(claim_name)
    if val is not None:
      return str(val)
  except Exception:
    pass
  return None


def is_token_fresh(credentials: CodexCredentials, now_ts: float | None = None) -> bool:
  """Check whether Codex access token is fresh enough for direct usage fetch.

  Stale rule:
  - If JWT exp exists: exp <= now + 300 seconds -> stale
  - Otherwise: last_refresh missing, invalid, or older than 8 days -> stale
  """
  current_time = time.time() if now_ts is None else now_ts
  exp = decode_jwt_exp(credentials.access_token)

  if exp is not None:
    return exp > (current_time + 300)

  # Fallback to last_refresh
  if not credentials.last_refresh:
    return False

  try:
    # Accept ISO strings with Z or timezone offset
    cleaned_time = credentials.last_refresh.replace("Z", "+00:00")
    dt = datetime.fromisoformat(cleaned_time)
    refresh_ts = dt.timestamp()
    # 8 days = 8 * 86400 = 691200 seconds
    return (current_time - refresh_ts) < 691200
  except Exception:
    return False


def load_codex_credentials(codex_home: str | None = None) -> CodexCredentials | None:
  """Read Codex credentials from auth.json strictly in read-only mode."""
  auth_path = get_codex_auth_path(codex_home)
  if not auth_path.is_file():
    return None

  try:
    with auth_path.open("r", encoding="utf-8") as f:
      data = json.load(f)

    tokens = data.get("tokens", {})
    if not isinstance(tokens, dict):
      return None

    access_token = tokens.get("access_token")
    if not access_token or not isinstance(access_token, str):
      return None

    account_id = tokens.get("account_id")
    account_id_str = str(account_id) if account_id is not None else None

    last_refresh = data.get("last_refresh")
    last_refresh_str = str(last_refresh) if last_refresh is not None else None

    id_token = tokens.get("id_token")
    email: str | None = None
    if id_token and isinstance(id_token, str):
      email = extract_jwt_claim(id_token, "email")
    if not email:
      email = extract_jwt_claim(access_token, "email")

    return CodexCredentials(
      access_token=access_token,
      account_id=account_id_str,
      last_refresh=last_refresh_str,
      email=email,
    )
  except Exception:
    return None
