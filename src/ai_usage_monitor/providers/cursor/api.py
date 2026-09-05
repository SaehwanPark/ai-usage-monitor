"""Cursor dashboard and usage API clients."""

from __future__ import annotations

from typing import Any
import httpx


class CursorAuthError(Exception):
  """Raised when Cursor cookie / session authentication fails (HTTP 401 or 403)."""


def fetch_cursor_api_data(
  cookie_header: str,
  timeout_seconds: float = 10.0,
) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None]:
  """Fetch usage summary, auth/me, and optional grok/legacy endpoints from cursor.com.

  Returns (usage_summary, me_data, sand_data, legacy_data).
  """
  headers = {
    "Accept": "application/json",
    "Cookie": cookie_header,
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CursorBar/1.0",
  }

  usage_summary: dict[str, Any] = {}
  me_data: dict[str, Any] | None = None
  sand_data: dict[str, Any] | None = None
  legacy_data: dict[str, Any] | None = None

  with httpx.Client(timeout=timeout_seconds) as client:
    # 1. Required: usage-summary
    try:
      resp = client.get("https://cursor.com/api/usage-summary", headers=headers)
    except httpx.TimeoutException as exc:
      raise TimeoutError(f"Request to Cursor usage-summary timed out after {timeout_seconds}s") from exc
    except httpx.RequestError as exc:
      raise ConnectionError(f"Network error contacting Cursor usage-summary: {exc}") from exc

    if resp.status_code in (401, 403):
      raise CursorAuthError(f"Cursor session cookie rejected (HTTP {resp.status_code})")

    if resp.status_code != 200:
      raise RuntimeError(f"Cursor usage-summary returned HTTP {resp.status_code}")

    try:
      usage_summary = resp.json()
    except Exception as exc:
      raise ValueError("Invalid JSON received from Cursor usage-summary") from exc

    # 2. Optional: auth/me
    try:
      me_resp = client.get("https://cursor.com/api/auth/me", headers=headers, timeout=min(timeout_seconds, 5.0))
      if me_resp.status_code == 200:
        me_data = me_resp.json()
    except Exception:
      pass

    # 3. Optional: Grok Bot / Sand quota
    try:
      sand_headers = {
        **headers,
        "Content-Type": "application/json",
        "Origin": "https://cursor.com",
      }
      sand_resp = client.post(
        "https://cursor.com/api/dashboard/get-sand-usage-status",
        headers=sand_headers,
        json={},
        timeout=min(timeout_seconds, 5.0),
      )
      if sand_resp.status_code == 200:
        sand_data = sand_resp.json()
    except Exception:
      pass

    # 4. Optional: legacy usage if sub is known
    sub = (me_data or {}).get("sub")
    if sub:
      try:
        leg_resp = client.get(
          f"https://cursor.com/api/usage?user={sub}",
          headers=headers,
          timeout=min(timeout_seconds, 5.0),
        )
        if leg_resp.status_code == 200:
          legacy_data = leg_resp.json()
      except Exception:
        pass

  return usage_summary, me_data, sand_data, legacy_data
