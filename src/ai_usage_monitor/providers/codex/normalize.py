"""Normalization functions for OpenAI Codex quota responses."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from ai_usage_monitor.model import (
  AccountIdentity,
  Credits,
  ProviderUsage,
  UsageWindow,
  create_unknown_window,
  create_window_from_percent,
)


def _format_timestamp(ts: int | float | None) -> str | None:
  """Convert Unix timestamp integer/float to ISO 8601 RFC3339 UTC string."""
  if ts is None:
    return None
  try:
    dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
  except Exception:
    return None


def _now_utc() -> str:
  """Current UTC timestamp as RFC3339 string."""
  return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_balance(val: Any) -> float | str | None:
  """Parse balance which may be string or float."""
  if val is None:
    return None
  try:
    return round(float(val), 2)
  except (ValueError, TypeError):
    return str(val)


def normalize_codex_oauth_response(payload: dict[str, Any]) -> ProviderUsage:
  """Normalize response from GET https://chatgpt.com/backend-api/wham/usage."""
  email = payload.get("email")
  user_id = payload.get("user_id")
  plan_type = payload.get("plan_type")

  account = AccountIdentity(
    id=str(user_id) if user_id else None,
    email=str(email) if email else None,
    plan=str(plan_type) if plan_type else None,
  )

  windows: list[UsageWindow] = []
  rate_limit = payload.get("rate_limit", {})

  # Primary window (session / 5-hour)
  primary = rate_limit.get("primary_window")
  if primary and isinstance(primary, dict):
    used_pct = primary.get("used_percent")
    win_sec = primary.get("limit_window_seconds", 18000)
    reset_at = _format_timestamp(primary.get("reset_at"))
    label = "5-hour" if win_sec == 18000 else f"{win_sec // 3600}h"
    if used_pct is not None:
      windows.append(
        create_window_from_percent(
          window_id="session",
          label=label,
          used_percent=float(used_pct),
          window_seconds=win_sec,
          resets_at=reset_at,
        )
      )
    else:
      windows.append(create_unknown_window(window_id="session", label=label, window_seconds=win_sec))

  # Secondary window (weekly)
  secondary = rate_limit.get("secondary_window")
  if secondary and isinstance(secondary, dict):
    used_pct = secondary.get("used_percent")
    win_sec = secondary.get("limit_window_seconds", 604800)
    reset_at = _format_timestamp(secondary.get("reset_at"))
    label = "Weekly" if win_sec == 604800 else f"{win_sec // 86400}d"
    if used_pct is not None:
      windows.append(
        create_window_from_percent(
          window_id="weekly",
          label=label,
          used_percent=float(used_pct),
          window_seconds=win_sec,
          resets_at=reset_at,
        )
      )
    else:
      windows.append(create_unknown_window(window_id="weekly", label=label, window_seconds=win_sec))

  # Additional rate limits (e.g. Spark / model-specific)
  additional = payload.get("additional_rate_limits", [])
  if isinstance(additional, list):
    for item in additional:
      if not isinstance(item, dict):
        continue
      limit_name = item.get("limit_name") or item.get("metered_feature") or "Additional Limit"
      item_rl = item.get("rate_limit", {})
      if isinstance(item_rl, dict):
        item_prim = item_rl.get("primary_window")
        if item_prim and isinstance(item_prim, dict):
          used_pct = item_prim.get("used_percent")
          win_sec = item_prim.get("limit_window_seconds")
          reset_at = _format_timestamp(item_prim.get("reset_at"))
          if used_pct is not None:
            windows.append(
              create_window_from_percent(
                window_id=f"additional_{limit_name.lower().replace(' ', '_')}",
                label=str(limit_name),
                used_percent=float(used_pct),
                window_seconds=win_sec,
                resets_at=reset_at,
              )
            )

  # Credits
  credits_obj: Credits | None = None
  raw_credits = payload.get("credits")
  if isinstance(raw_credits, dict):
    credits_obj = Credits(
      has_credits=bool(raw_credits.get("has_credits", False)),
      unlimited=bool(raw_credits.get("unlimited", False)),
      balance=_parse_balance(raw_credits.get("balance")),
    )

  return ProviderUsage(
    provider="codex",
    account=account,
    source="codex_oauth",
    windows=windows,
    credits=credits_obj,
    spend=None,
    fetched_at=_now_utc(),
    warnings=[],
  )


def normalize_codex_rpc_response(account_data: dict[str, Any], rate_limits_data: dict[str, Any]) -> ProviderUsage:
  """Normalize responses from codex app-server JSON-RPC account/read and account/rateLimits/read."""
  acct_obj = account_data.get("account", {})
  email = acct_obj.get("email")
  plan_type = acct_obj.get("planType") or acct_obj.get("plan_type")

  account = AccountIdentity(
    id=None,
    email=str(email) if email else None,
    plan=str(plan_type) if plan_type else None,
  )

  rl_obj = rate_limits_data.get("rateLimits", {})
  if not plan_type and rl_obj.get("planType"):
    account = AccountIdentity(id=account.id, email=account.email, plan=str(rl_obj.get("planType")))

  windows: list[UsageWindow] = []

  # Primary (session)
  primary = rl_obj.get("primary")
  if primary and isinstance(primary, dict):
    used_pct = primary.get("usedPercent") if "usedPercent" in primary else primary.get("used_percent")
    duration_mins = (
      primary.get("windowDurationMins") if "windowDurationMins" in primary else primary.get("window_duration_mins", 300)
    )
    win_sec = duration_mins * 60 if duration_mins else 18000
    resets_at_raw = primary.get("resetsAt") if "resetsAt" in primary else primary.get("resets_at")
    reset_at = _format_timestamp(resets_at_raw)
    label = "5-hour" if win_sec == 18000 else f"{win_sec // 3600}h"
    if used_pct is not None:
      windows.append(
        create_window_from_percent(
          window_id="session",
          label=label,
          used_percent=float(used_pct),
          window_seconds=win_sec,
          resets_at=reset_at,
        )
      )
    else:
      windows.append(create_unknown_window(window_id="session", label=label, window_seconds=win_sec))

  # Secondary (weekly)
  secondary = rl_obj.get("secondary")
  if secondary and isinstance(secondary, dict):
    used_pct = secondary.get("usedPercent") if "usedPercent" in secondary else secondary.get("used_percent")
    duration_mins = (
      secondary.get("windowDurationMins")
      if "windowDurationMins" in secondary
      else secondary.get("window_duration_mins", 10080)
    )
    win_sec = duration_mins * 60 if duration_mins else 604800
    resets_at_raw = secondary.get("resetsAt") if "resetsAt" in secondary else secondary.get("resets_at")
    reset_at = _format_timestamp(resets_at_raw)
    label = "Weekly" if win_sec == 604800 else f"{win_sec // 86400}d"
    if used_pct is not None:
      windows.append(
        create_window_from_percent(
          window_id="weekly",
          label=label,
          used_percent=float(used_pct),
          window_seconds=win_sec,
          resets_at=reset_at,
        )
      )
    else:
      windows.append(create_unknown_window(window_id="weekly", label=label, window_seconds=win_sec))

  # Additional rate limits by limit ID
  by_limit_id = rate_limits_data.get("rateLimitsByLimitId") or rate_limits_data.get("rate_limits_by_limit_id") or {}
  if isinstance(by_limit_id, dict):
    for limit_id, val in by_limit_id.items():
      if limit_id == "codex" or not isinstance(val, dict):
        continue
      limit_name = val.get("limitName") or val.get("limit_name") or limit_id
      val_prim = val.get("primary")
      if val_prim and isinstance(val_prim, dict):
        used_pct = val_prim.get("usedPercent") if "usedPercent" in val_prim else val_prim.get("used_percent")
        duration_mins = (
          val_prim.get("windowDurationMins")
          if "windowDurationMins" in val_prim
          else val_prim.get("window_duration_mins")
        )
        win_sec = duration_mins * 60 if duration_mins else None
        resets_at_raw = val_prim.get("resetsAt") if "resetsAt" in val_prim else val_prim.get("resets_at")
        reset_at = _format_timestamp(resets_at_raw)
        if used_pct is not None:
          windows.append(
            create_window_from_percent(
              window_id=f"additional_{limit_id}",
              label=str(limit_name),
              used_percent=float(used_pct),
              window_seconds=win_sec,
              resets_at=reset_at,
            )
          )

  # Credits
  credits_obj: Credits | None = None
  raw_credits = rl_obj.get("credits")
  if isinstance(raw_credits, dict):
    has_credits = raw_credits.get("hasCredits") if "hasCredits" in raw_credits else raw_credits.get("has_credits", False)
    credits_obj = Credits(
      has_credits=bool(has_credits),
      unlimited=bool(raw_credits.get("unlimited", False)),
      balance=_parse_balance(raw_credits.get("balance")),
    )

  return ProviderUsage(
    provider="codex",
    account=account,
    source="codex_rpc",
    windows=windows,
    credits=credits_obj,
    spend=None,
    fetched_at=_now_utc(),
    warnings=[],
  )
