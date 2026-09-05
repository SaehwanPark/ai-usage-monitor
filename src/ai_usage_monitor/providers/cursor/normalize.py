"""Normalization for Cursor dashboard and usage-summary responses."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from ai_usage_monitor.model import (
  AccountIdentity,
  ProviderUsage,
  Spend,
  UsageWindow,
  create_unknown_window,
  create_window_from_percent,
)


def _parse_iso_to_utc_str(ts_str: str | None) -> tuple[str | None, float | None]:
  """Parse ISO timestamp with or without fractional seconds into RFC3339 UTC string and epoch timestamp."""
  if not ts_str:
    return None, None
  try:
    clean = ts_str.replace("Z", "+00:00")
    dt = datetime.fromisoformat(clean)
    utc_dt = dt.astimezone(timezone.utc)
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ"), utc_dt.timestamp()
  except Exception:
    return ts_str, None


def _now_utc() -> str:
  return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _resolve_headline_percent(plan: dict[str, Any], overall: dict[str, Any], pooled: dict[str, Any]) -> float | None:
  """Resolve headline usage percentage according to specification precedence."""
  if plan.get("totalPercentUsed") is not None:
    return float(plan["totalPercentUsed"])

  auto = plan.get("autoPercentUsed")
  api = plan.get("apiPercentUsed")
  if auto is not None and api is not None:
    return (float(auto) + float(api)) / 2.0
  if api is not None:
    return float(api)
  if auto is not None:
    return float(auto)

  plan_limit = plan.get("limit")
  plan_used = plan.get("used")
  if plan_limit and float(plan_limit) > 0 and plan_used is not None:
    return 100.0 * float(plan_used) / float(plan_limit)

  overall_limit = overall.get("limit")
  overall_used = overall.get("used")
  if overall_limit and float(overall_limit) > 0 and overall_used is not None:
    return 100.0 * float(overall_used) / float(overall_limit)

  pooled_limit = pooled.get("limit")
  pooled_used = pooled.get("used")
  if pooled_limit and float(pooled_limit) > 0 and pooled_used is not None:
    return 100.0 * float(pooled_used) / float(pooled_limit)

  return None


def normalize_cursor_usage(
  usage_summary: dict[str, Any],
  me_data: dict[str, Any] | None = None,
  sand_data: dict[str, Any] | None = None,
  legacy_data: dict[str, Any] | None = None,
  source: str = "cursor_app_token",
) -> ProviderUsage:
  """Normalize Cursor API responses into standard ProviderUsage."""
  # Account resolution
  me = me_data or {}
  email = me.get("email")
  sub = me.get("sub")
  membership = usage_summary.get("membershipType") or me.get("membershipType")

  account = AccountIdentity(
    id=str(sub) if sub else None,
    email=str(email) if email else None,
    plan=str(membership) if membership else None,
  )

  # Reset and window calculation
  cycle_start_str = usage_summary.get("billingCycleStart")
  cycle_end_str = usage_summary.get("billingCycleEnd")
  start_rfc, start_ts = _parse_iso_to_utc_str(cycle_start_str)
  end_rfc, end_ts = _parse_iso_to_utc_str(cycle_end_str)

  window_seconds: int | None = None
  if start_ts is not None and end_ts is not None and end_ts > start_ts:
    window_seconds = int(end_ts - start_ts)

  windows: list[UsageWindow] = []

  # Check legacy request plan first
  has_legacy_plan = False
  if legacy_data and isinstance(legacy_data, dict):
    gpt4 = legacy_data.get("gpt-4", {})
    if isinstance(gpt4, dict):
      req_used = gpt4.get("numRequestsTotal")
      if req_used is None:
        req_used = gpt4.get("numRequests")
      req_limit = gpt4.get("maxRequestUsage")
      if req_limit and float(req_limit) > 0 and req_used is not None:
        has_legacy_plan = True
        pct = 100.0 * float(req_used) / float(req_limit)
        windows.append(
          create_window_from_percent(
            window_id="requests",
            label="Requests",
            used_percent=pct,
            window_seconds=window_seconds,
            resets_at=end_rfc,
          )
        )

  # Modern percentage plan
  if not has_legacy_plan:
    indiv = usage_summary.get("individualUsage", {})
    plan = indiv.get("plan", {}) if isinstance(indiv, dict) else {}
    overall = indiv.get("overall", {}) if isinstance(indiv, dict) else {}
    team = usage_summary.get("teamUsage", {})
    pooled = team.get("pooled", {}) if isinstance(team, dict) else {}

    headline_pct = _resolve_headline_percent(plan, overall, pooled)
    if headline_pct is not None:
      windows.append(
        create_window_from_percent(
          window_id="total",
          label="Total",
          used_percent=headline_pct,
          window_seconds=window_seconds,
          resets_at=end_rfc,
        )
      )
    else:
      windows.append(
        create_unknown_window(
          window_id="total",
          label="Total",
          window_seconds=window_seconds,
          resets_at=end_rfc,
        )
      )

    # Secondary: Cursor / Composer lane
    auto_pct = plan.get("autoPercentUsed")
    if auto_pct is not None:
      windows.append(
        create_window_from_percent(
          window_id="cursor_auto",
          label="Cursor",
          used_percent=float(auto_pct),
          window_seconds=window_seconds,
          resets_at=end_rfc,
        )
      )

    # Tertiary: Third Party / API lane
    api_pct = plan.get("apiPercentUsed")
    if api_pct is not None:
      windows.append(
        create_window_from_percent(
          window_id="cursor_api",
          label="Third Party",
          used_percent=float(api_pct),
          window_seconds=window_seconds,
          resets_at=end_rfc,
        )
      )

  # Optional Grok Bot / Sand quota
  if sand_data and isinstance(sand_data, dict):
    sand_pct = sand_data.get("usagePercent")
    if sand_pct is not None:
      reset_raw = sand_data.get("nextResetTimestampUtc")
      sand_reset, _ = _parse_iso_to_utc_str(reset_raw)
      windows.append(
        create_window_from_percent(
          window_id="grok_bot",
          label="Grok Bot",
          used_percent=float(sand_pct),
          window_seconds=604800,
          resets_at=sand_reset,
        )
      )

  # On-demand spend calculation
  spend_obj: Spend | None = None
  indiv_obj = usage_summary.get("individualUsage", {})
  indiv_ondemand = indiv_obj.get("onDemand", {}) if isinstance(indiv_obj, dict) else {}
  team_obj = usage_summary.get("teamUsage", {})
  team_ondemand = team_obj.get("onDemand", {}) if isinstance(team_obj, dict) else {}

  ondemand_used = indiv_ondemand.get("used")
  ondemand_limit = indiv_ondemand.get("limit")
  if (not ondemand_limit or float(ondemand_limit) <= 0) and team_ondemand:
    ondemand_used = team_ondemand.get("used")
    ondemand_limit = team_ondemand.get("limit")

  if ondemand_used is not None or ondemand_limit is not None:
    spend_obj = Spend(
      used_usd=round(float(ondemand_used) / 100.0, 2) if ondemand_used is not None else None,
      limit_usd=round(float(ondemand_limit) / 100.0, 2) if ondemand_limit is not None else None,
      period="billing-cycle",
    )

  return ProviderUsage(
    provider="cursor",
    account=account,
    source=source,
    windows=windows,
    credits=None,
    spend=spend_obj,
    fetched_at=_now_utc(),
    warnings=[],
  )
