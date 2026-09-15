"""Cursor provider orchestrator."""

from __future__ import annotations

from datetime import datetime, timezone
from ai_usage_monitor.config import load_config
from ai_usage_monitor.model import ProviderUsage
from ai_usage_monitor.providers.cursor.api import CursorAuthError, fetch_cursor_api_data
from ai_usage_monitor.providers.cursor.cli_auth import read_cursor_cli_credentials
from ai_usage_monitor.providers.cursor.db import read_cursor_access_token, read_cursor_cached_email
from ai_usage_monitor.providers.cursor.normalize import normalize_cursor_usage
from ai_usage_monitor.providers.cursor.session import derive_session_cookie, parse_cursor_jwt


def _now_utc() -> str:
  return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _try_fetch_with_token(
  token: str,
  source_name: str,
  fallback_email: str | None = None,
  timeout_seconds: float = 10.0,
) -> ProviderUsage | None:
  """Attempt fetching and normalizing Cursor usage using a raw JWT access token."""
  claims = parse_cursor_jwt(token)
  if not claims or not claims.is_fresh:
    return None

  cookie_header = derive_session_cookie(claims.user_id, token)
  try:
    usage_summary, me_data, sand_data, legacy_data = fetch_cursor_api_data(
      cookie_header=cookie_header,
      timeout_seconds=timeout_seconds,
    )
    email = fallback_email or claims.email
    if me_data is None and email:
      me_data = {"email": email, "sub": claims.sub}
    elif me_data is not None and not me_data.get("email") and email:
      me_data["email"] = email

    return normalize_cursor_usage(
      usage_summary=usage_summary,
      me_data=me_data,
      sand_data=sand_data,
      legacy_data=legacy_data,
      source=source_name,
    )
  except CursorAuthError:
    return None
  except Exception as exc:
    return ProviderUsage(
      provider="cursor",
      account=None,
      source=source_name,
      windows=[],
      credits=None,
      spend=None,
      fetched_at=_now_utc(),
      warnings=[],
      error=str(exc),
    )


def fetch_cursor_usage(
  cookie_override: str | None = None,
  source_preference: str = "auto",
  timeout_seconds: float = 10.0,
) -> ProviderUsage:
  """Retrieve current Cursor subscription usage quota.

  Supports automatic discovery across:
  1. User-supplied manual cookie override.
  2. Cursor Desktop application state database (state.vscdb).
  3. Cursor CLI credentials (macOS Keychain or file-based auth.json).
  4. Configured cookie from config file or environment variable.
  """
  pref = source_preference.lower()

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
  desktop_token = read_cursor_access_token() if pref in ("auto", "desktop", "app") else None
  desktop_claims = parse_cursor_jwt(desktop_token) if desktop_token else None

  if desktop_token and desktop_claims and desktop_claims.is_fresh:
    desktop_email = desktop_claims.email or read_cursor_cached_email()
    desktop_res = _try_fetch_with_token(
      token=desktop_token,
      source_name="cursor_app_token",
      fallback_email=desktop_email,
      timeout_seconds=timeout_seconds,
    )
    if desktop_res:
      return desktop_res

  # If user specifically requested desktop and it failed:
  if pref in ("desktop", "app"):
    if desktop_token and desktop_claims and not desktop_claims.is_fresh:
      msg = "Cursor desktop access token in state.vscdb has expired. Restart Cursor desktop to refresh session."
    elif desktop_token and not desktop_claims:
      msg = "Cursor desktop access token in state.vscdb is malformed."
    else:
      msg = "Cursor desktop credentials not found in state.vscdb."
    return ProviderUsage(
      provider="cursor",
      account=None,
      source="cursor_desktop",
      windows=[],
      credits=None,
      spend=None,
      fetched_at=_now_utc(),
      warnings=[],
      error=msg,
    )

  # 3. Cursor CLI credentials (macOS Keychain or ~/.cursor/auth.json)
  cli_creds = read_cursor_cli_credentials() if pref in ("auto", "cli", "agent") else None
  cli_claims = parse_cursor_jwt(cli_creds.access_token) if cli_creds else None

  if cli_creds and cli_claims and cli_claims.is_fresh:
    cli_email = cli_claims.email or cli_creds.email
    cli_res = _try_fetch_with_token(
      token=cli_creds.access_token,
      source_name="cursor_cli_token",
      fallback_email=cli_email,
      timeout_seconds=timeout_seconds,
    )
    if cli_res:
      return cli_res

  # If user specifically requested CLI and it failed:
  if pref in ("cli", "agent"):
    if cli_creds and cli_claims and not cli_claims.is_fresh:
      msg = "Cursor CLI access token has expired. Run `cursor login` to refresh session."
    elif cli_creds and not cli_claims:
      msg = "Cursor CLI access token is malformed."
    else:
      msg = "Cursor CLI credentials not found in Keychain or auth file. Run `cursor login` to authenticate."
    return ProviderUsage(
      provider="cursor",
      account=None,
      source="cursor_cli",
      windows=[],
      credits=None,
      spend=None,
      fetched_at=_now_utc(),
      warnings=[],
      error=msg,
    )

  # 4. Check configured manual cookie from config file or environment variable
  cfg = load_config()
  if cfg.cursor_cookie and pref in ("auto", "cookie"):
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

  # Neither path succeeded in auto mode
  if desktop_token and desktop_claims and not desktop_claims.is_fresh:
    msg = (
      "Cursor desktop access token in state.vscdb has expired. "
      "Please focus or restart Cursor desktop, run `cursor login`, or configure LLM_USAGE_CURSOR_COOKIE."
    )
  elif cli_creds and cli_claims and not cli_claims.is_fresh:
    msg = (
      "Cursor CLI access token has expired. "
      "Please run `cursor login`, restart Cursor desktop, or configure LLM_USAGE_CURSOR_COOKIE."
    )
  else:
    msg = (
      "Cursor credentials not found in Desktop database (state.vscdb) or CLI credential store. "
      "Please log into Cursor, run `cursor login`, or configure LLM_USAGE_CURSOR_COOKIE."
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
