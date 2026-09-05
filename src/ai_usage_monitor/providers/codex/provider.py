"""OpenAI Codex provider orchestrator."""

from __future__ import annotations

from datetime import datetime, timezone
from ai_usage_monitor.model import ProviderUsage
from ai_usage_monitor.providers.codex.auth import (
  is_token_fresh,
  load_codex_credentials,
)
from ai_usage_monitor.providers.codex.oauth import CodexAuthError, fetch_codex_oauth_usage
from ai_usage_monitor.providers.codex.rpc import fetch_codex_rpc_usage
from ai_usage_monitor.windows.paths import resolve_codex_binary


def _now_utc() -> str:
  return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_codex_usage(
  source_preference: str = "auto",
  codex_home: str | None = None,
  timeout_seconds: float = 10.0,
) -> ProviderUsage:
  """Retrieve current OpenAI Codex subscription usage quota."""
  pref = source_preference.lower()

  if pref in ("cli", "rpc"):
    try:
      return fetch_codex_rpc_usage(timeout_seconds=timeout_seconds)
    except Exception as exc:
      return ProviderUsage(
        provider="codex",
        account=None,
        source="codex_rpc",
        windows=[],
        credits=None,
        spend=None,
        fetched_at=_now_utc(),
        warnings=[],
        error=f"Codex CLI RPC error: {exc}",
      )

  if pref == "oauth":
    creds = load_codex_credentials(codex_home=codex_home)
    if not creds:
      return ProviderUsage(
        provider="codex",
        account=None,
        source="codex_oauth",
        windows=[],
        credits=None,
        spend=None,
        fetched_at=_now_utc(),
        warnings=[],
        error="Codex credentials not found in auth.json",
      )
    try:
      return fetch_codex_oauth_usage(creds, timeout_seconds=timeout_seconds)
    except Exception as exc:
      return ProviderUsage(
        provider="codex",
        account=None,
        source="codex_oauth",
        windows=[],
        credits=None,
        spend=None,
        fetched_at=_now_utc(),
        warnings=[],
        error=f"Codex OAuth error: {exc}",
      )

  # AUTO mode:
  # 1. Try OAuth if credentials exist
  creds = load_codex_credentials(codex_home=codex_home)
  if creds and is_token_fresh(creds):
    try:
      return fetch_codex_oauth_usage(creds, timeout_seconds=timeout_seconds)
    except CodexAuthError:
      # Token was rejected, try fallback to CLI RPC
      pass
    except Exception as exc:
      # Network/schema/5xx error: surface original error (fail-closed)
      return ProviderUsage(
        provider="codex",
        account=None,
        source="codex_oauth",
        windows=[],
        credits=None,
        spend=None,
        fetched_at=_now_utc(),
        warnings=[],
        error=str(exc),
      )

  # 2. Try CLI RPC if available
  codex_bin = resolve_codex_binary()
  if codex_bin:
    try:
      return fetch_codex_rpc_usage(codex_bin=codex_bin, timeout_seconds=timeout_seconds)
    except Exception as exc:
      return ProviderUsage(
        provider="codex",
        account=None,
        source="codex_rpc",
        windows=[],
        credits=None,
        spend=None,
        fetched_at=_now_utc(),
        warnings=[],
        error=f"Codex CLI app-server error: {exc}",
      )

  # Neither path succeeded
  return ProviderUsage(
    provider="codex",
    account=None,
    source="codex_auto",
    windows=[],
    credits=None,
    spend=None,
    fetched_at=_now_utc(),
    warnings=[],
    error=(
      "Codex credentials not found or expired, and codex CLI not installed. "
      "Please install/sign-in with Codex CLI or verify auth.json."
    ),
  )
