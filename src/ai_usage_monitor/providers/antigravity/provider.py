"""Antigravity provider orchestrator."""

from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Any
from ai_usage_monitor.config import load_config
from ai_usage_monitor.model import ProviderUsage
from ai_usage_monitor.providers.antigravity.client import post_loopback_json
from ai_usage_monitor.providers.antigravity.discovery import manage_agy_session
from ai_usage_monitor.providers.antigravity.normalize import (
  normalize_antigravity_quota_summary,
  normalize_antigravity_user_status_legacy,
)
from ai_usage_monitor.windows.paths import resolve_agy_binary


def _now_utc() -> str:
  return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _probe_port(port: int, timeout_seconds: float) -> ProviderUsage | None:
  """Probe a single localhost port for Antigravity quota endpoints."""
  # 1. Preferred: RetrieveUserQuotaSummary
  summary_data: dict[str, Any] | None = None
  for force_refresh in (True, False):
    try:
      summary_data = post_loopback_json(
        port=port,
        path="/exa.language_server_pb.LanguageServerService/RetrieveUserQuotaSummary",
        payload={"forceRefresh": force_refresh},
        timeout_seconds=min(timeout_seconds, 4.0),
      )
      if summary_data and summary_data.get("response", {}).get("groups"):
        break
    except Exception:
      pass

  groups = (summary_data or {}).get("response", {}).get("groups", [])
  if summary_data and groups:
    # Quota summary succeeded! Enrich with GetUserStatus
    user_status_data: dict[str, Any] | None = None
    try:
      user_status_data = post_loopback_json(
        port=port,
        path="/exa.language_server_pb.LanguageServerService/GetUserStatus",
        payload={
          "metadata": {
            "ideName": "antigravity",
            "extensionName": "antigravity",
            "ideVersion": "unknown",
            "locale": "en",
          }
        },
        timeout_seconds=min(timeout_seconds, 3.0),
      )
    except Exception:
      pass

    norm = normalize_antigravity_quota_summary(
      summary_data=summary_data,
      user_status_data=user_status_data,
      source="antigravity_agy",
    )
    if norm.windows:
      return norm

  # 2. Fallback 1: GetUserStatus
  user_status_data = None
  try:
    user_status_data = post_loopback_json(
      port=port,
      path="/exa.language_server_pb.LanguageServerService/GetUserStatus",
      payload={
        "metadata": {
          "ideName": "antigravity",
          "extensionName": "antigravity",
          "ideVersion": "unknown",
          "locale": "en",
        }
      },
      timeout_seconds=min(timeout_seconds, 3.0),
    )
  except Exception:
    pass

  if user_status_data and user_status_data.get("userStatus", {}).get("cascadeModelConfigData"):
    norm_status = normalize_antigravity_user_status_legacy(
      user_status_data=user_status_data,
      source="antigravity_agy",
    )
    if norm_status.windows:
      return norm_status

  # 3. Fallback 2: GetCommandModelConfigs
  cmd_configs_data = None
  try:
    cmd_configs_data = post_loopback_json(
      port=port,
      path="/exa.language_server_pb.LanguageServerService/GetCommandModelConfigs",
      payload={
        "metadata": {
          "ideName": "antigravity",
          "extensionName": "antigravity",
          "ideVersion": "unknown",
          "locale": "en",
        }
      },
      timeout_seconds=min(timeout_seconds, 3.0),
    )
  except Exception:
    pass

  if cmd_configs_data and cmd_configs_data.get("clientModelConfigs"):
    wrapped = {"userStatus": {"cascadeModelConfigData": cmd_configs_data}}
    norm_cmd = normalize_antigravity_user_status_legacy(
      user_status_data=wrapped,
      source="antigravity_agy",
    )
    if norm_cmd.windows:
      return norm_cmd

  return None


def fetch_antigravity_usage(
  cli_path: str | None = None,
  timeout_seconds: float = 10.0,
) -> ProviderUsage:
  """Retrieve current Google Antigravity subscription usage quota via agy."""
  cfg = load_config()
  configured_cli = cli_path or cfg.antigravity_cli

  binary = resolve_agy_binary(configured_cli)
  if not binary:
    return ProviderUsage(
      provider="antigravity",
      account=None,
      source="antigravity_agy",
      windows=[],
      credits=None,
      spend=None,
      fetched_at=_now_utc(),
      warnings=[],
      error="Google Antigravity CLI ('agy') is not installed or not in PATH. Please install agy.",
    )

  with manage_agy_session(configured_path=configured_cli, startup_timeout=timeout_seconds) as candidate_ports:
    if not candidate_ports:
      return ProviderUsage(
        provider="antigravity",
        account=None,
        source="antigravity_agy",
        windows=[],
        credits=None,
        spend=None,
        fetched_at=_now_utc(),
        warnings=[],
        error="Antigravity local service is not listening. Run `agy` once in a terminal and complete Google sign-in.",
      )

    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
      for port in candidate_ports:
        remaining_time = max(1.0, deadline - time.time())
        res = _probe_port(port, timeout_seconds=min(remaining_time, 4.0))
        if res is not None and res.windows:
          return res
      if time.time() >= deadline:
        break
      time.sleep(0.4)

  return ProviderUsage(
    provider="antigravity",
    account=None,
    source="antigravity_agy",
    windows=[],
    credits=None,
    spend=None,
    fetched_at=_now_utc(),
    warnings=[],
    error=(
      "Antigravity local quota service was reached but returned no usable quota. "
      "Please verify your agy login status."
    ),
  )
