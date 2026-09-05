"""Cursor provider orchestrator."""

from __future__ import annotations

from datetime import datetime, timezone
from ai_usage_monitor.config import load_config
from ai_usage_monitor.model import ProviderUsage
from ai_usage_monitor.providers.cursor.api import CursorAuthError, fetch_cursor_api_data
from ai_usage_monitor.providers.cursor.db import read_cursor_access_token
from ai_usage_monitor.providers.cursor.normalize import normalize_cursor_usage
from ai_usage_monitor.providers.cursor.session import derive_session_cookie, parse_cursor_jwt


def _now_utc() -> str:
  return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_cursor_usage(
  cookie_override: str | None = None,
  timeout_seconds: float = 10.0,
) -> ProviderUsage:
  """Retrieve current Cursor subscription usage quota."""
  # 1. Manual cookie override supplied via argument
  if cookie_override:
    cookie_header = cookie_override
    if not cookie_header.lower().startswith("workoscursorsessiontoken=") and "=" not in cookie_header:
      cookie_header = f"WorkosCursorSessionToken={cookie_override}"
    try:
      usage_summary, me_data, sand_data, legacy_data = fetch_cursor_api_data(
        cookie_header=cookie_header,
        timeout_seconds=timeout_seconds,
      )
      return normalize_cursor_usage(
        usage_summary=usage_summary,
        me_data=me_data,
        sand_data=sand_data,
        legacy_data=legacy_data,
        source="cursor_manual_cookie",
      )
    except Exception as exc:
      return ProviderUsage(
        provider="cursor",
        account=None,
        source="cursor_manual_cookie",
        windows=[],
        credits=None,
        spend=None,
        fetched_at=_now_utc(),
        warnings=[],
        error=f"Cursor manual cookie error: {exc}",
      )

  # 2. Local desktop app token from state.vscdb
  raw_token = read_cursor_access_token()
  claims = parse_cursor_jwt(raw_token) if raw_token else None

  if raw_token and claims and claims.is_fresh:
    cookie_header = derive_session_cookie(claims.user_id, raw_token)
    try:
      usage_summary, me_data, sand_data, legacy_data = fetch_cursor_api_data(
        cookie_header=cookie_header,
        timeout_seconds=timeout_seconds,
      )
      # If me_data email is missing, fall back to claims.email
      if me_data is None and claims.email:
        me_data = {"email": claims.email, "sub": claims.sub}
      elif me_data is not None and not me_data.get("email") and claims.email:
        me_data["email"] = claims.email

      return normalize_cursor_usage(
        usage_summary=usage_summary,
        me_data=me_data,
        sand_data=sand_data,
        legacy_data=legacy_data,
        source="cursor_app_token",
      )
    except CursorAuthError:
      # Token was rejected by server, will try config fallback next
      pass
    except Exception as exc:
      # Network/5xx error: fail closed
      return ProviderUsage(
        provider="cursor",
        account=None,
        source="cursor_app_token",
        windows=[],
        credits=None,
        spend=None,
        fetched_at=_now_utc(),
        warnings=[],
        error=str(exc),
      )

  # 3. Check configured manual cookie from config file or environment variable
  cfg = load_config()
  if cfg.cursor_cookie:
    cfg_cookie = cfg.cursor_cookie
    if not cfg_cookie.lower().startswith("workoscursorsessiontoken=") and "=" not in cfg_cookie:
      cfg_cookie = f"WorkosCursorSessionToken={cfg.cursor_cookie}"
    try:
      usage_summary, me_data, sand_data, legacy_data = fetch_cursor_api_data(
        cookie_header=cfg_cookie,
        timeout_seconds=timeout_seconds,
      )
      return normalize_cursor_usage(
        usage_summary=usage_summary,
        me_data=me_data,
        sand_data=sand_data,
        legacy_data=legacy_data,
        source="cursor_manual_cookie",
      )
    except Exception as exc:
      return ProviderUsage(
        provider="cursor",
        account=None,
        source="cursor_manual_cookie",
        windows=[],
        credits=None,
        spend=None,
        fetched_at=_now_utc(),
        warnings=[],
        error=f"Cursor configured cookie error: {exc}",
      )

  # Neither path succeeded
  if raw_token and claims and not claims.is_fresh:
    msg = (
      "Cursor desktop access token in state.vscdb has expired. "
      "Please open or restart Cursor to refresh session, or configure a cookie."
    )
  elif raw_token and not claims:
    msg = "Cursor desktop access token in state.vscdb is malformed."
  else:
    msg = (
      "Cursor desktop credentials not found in state.vscdb. "
      "Please log into Cursor, or configure LLM_USAGE_CURSOR_COOKIE."
    )

  return ProviderUsage(
    provider="cursor",
    account=None,
    source="cursor_auto",
    windows=[],
    credits=None,
    spend=None,
    fetched_at=_now_utc(),
    warnings=[],
    error=msg,
  )
