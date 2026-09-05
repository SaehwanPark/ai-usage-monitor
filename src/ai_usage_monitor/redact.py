"""Secret and token redaction utilities."""

from __future__ import annotations

from typing import Mapping


def redact_secret(val: str | None) -> str:
  """Redact sensitive token or password, revealing only prefix/suffix if long enough."""
  if not val:
    return ""
  if len(val) <= 8:
    return "[REDACTED]"
  return f"{val[:3]}...{val[-3:]}"


def redact_jwt(val: str | None) -> str:
  """Redact JWT token string preserving payload hint if needed, without revealing signature."""
  if not val:
    return ""
  parts = val.split(".")
  if len(parts) == 3:
    header = parts[0]
    return f"{header[:6]}...[REDACTED_PAYLOAD_AND_SIGNATURE]"
  return redact_secret(val)


def redact_headers(headers: Mapping[str, str]) -> dict[str, str]:
  """Return a copy of HTTP headers with sensitive headers redacted."""
  result: dict[str, str] = {}
  sensitive_keys = {"authorization", "cookie", "x-api-key", "token", "session-token"}
  for k, v in headers.items():
    if k.lower() in sensitive_keys:
      result[k] = redact_secret(v)
    else:
      result[k] = v
  return result
