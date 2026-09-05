"""Cursor JWT validation and web session cookie construction."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import json
import re
import time
import urllib.parse

_USER_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


@dataclass(frozen=True)
class CursorTokenClaims:
  sub: str
  user_id: str
  exp: int
  email: str | None
  is_fresh: bool


def extract_user_id_from_sub(sub: str) -> str | None:
  """Extract the last nonempty segment of sub and validate character set."""
  if not sub:
    return None
  parts = [p.strip() for p in sub.split("|") if p.strip()]
  if not parts:
    return None
  candidate = parts[-1]
  if _USER_ID_RE.match(candidate):
    return candidate
  return None


def parse_cursor_jwt(token: str, now_ts: float | None = None) -> CursorTokenClaims | None:
  """Decode Cursor JWT payload, extract claims, and evaluate freshness (> now + 60s)."""
  current_time = time.time() if now_ts is None else now_ts
  try:
    parts = token.split(".")
    if len(parts) < 2:
      return None
    payload_b64 = parts[1]
    payload_b64 += "=" * (-len(payload_b64) % 4)
    payload_bytes = base64.urlsafe_b64decode(payload_b64)
    payload = json.loads(payload_bytes)

    sub = payload.get("sub")
    exp = payload.get("exp")
    if not sub or not exp or not isinstance(exp, (int, float)):
      return None

    user_id = extract_user_id_from_sub(str(sub))
    if not user_id:
      return None

    exp_int = int(exp)
    email = payload.get("email")
    email_str = str(email) if email is not None else None

    # exp must be > now + 60s
    is_fresh = exp_int > (current_time + 60)

    return CursorTokenClaims(
      sub=str(sub),
      user_id=user_id,
      exp=exp_int,
      email=email_str,
      is_fresh=is_fresh,
    )
  except Exception:
    return None


def derive_session_cookie(user_id: str, access_token: str) -> str:
  """Construct Cursor web-session cookie header value."""
  encoded_segment = f"{user_id}::{access_token}"
  # URL encode the :: separator as %3A%3A
  encoded_value = urllib.parse.quote(encoded_segment, safe="")
  return f"WorkosCursorSessionToken={encoded_value}"
