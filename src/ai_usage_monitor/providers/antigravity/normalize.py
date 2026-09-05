"""Normalization functions for Google Antigravity quota and user status responses."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from ai_usage_monitor.model import (
  AccountIdentity,
  ProviderUsage,
  UsageWindow,
  create_window_from_fraction,
)


def _now_utc() -> str:
  return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _resolve_cadence(bucket_id: str, display_name: str, window: str | None) -> tuple[str, int]:
  """Resolve window cadence label suffix and window duration in seconds."""
  combined = f"{bucket_id} {display_name} {window or ''}".lower()
  if any(s in combined for s in ("5h", "session", "5-hour", "five hour", "five-hour")):
    return "5h", 18000
  if "weekly" in combined:
    return "weekly", 604800
  return "custom", 0


def _extract_account(user_status_data: dict[str, Any] | None) -> AccountIdentity | None:
  """Extract account email and tier/plan from GetUserStatus payload."""
  if not user_status_data:
    return None
  user_status = user_status_data.get("userStatus", {})
  if not isinstance(user_status, dict):
    return None

  email = user_status.get("email")
  tier_obj = user_status.get("userTier")
  tier_name: str | None = None
  if isinstance(tier_obj, dict):
    tier_name = tier_obj.get("name") or tier_obj.get("id")

  if not tier_name:
    plan_info = user_status.get("planStatus", {}).get("planInfo", {})
    if isinstance(plan_info, dict):
      tier_name = plan_info.get("planName")

  return AccountIdentity(
    id=None,
    email=str(email) if email else None,
    plan=str(tier_name) if tier_name else None,
  )


def normalize_antigravity_quota_summary(
  summary_data: dict[str, Any],
  user_status_data: dict[str, Any] | None = None,
  source: str = "antigravity_agy",
) -> ProviderUsage:
  """Normalize response from RetrieveUserQuotaSummary into ProviderUsage."""
  account = _extract_account(user_status_data)

  resp_obj = summary_data.get("response", {})
  groups = resp_obj.get("groups", [])
  windows: list[UsageWindow] = []

  if isinstance(groups, list):
    for grp in groups:
      if not isinstance(grp, dict):
        continue
      grp_name = grp.get("displayName", "")
      buckets = grp.get("buckets", [])
      if not isinstance(buckets, list):
        continue

      for bkt in buckets:
        if not isinstance(bkt, dict):
          continue
        bkt_id = bkt.get("bucketId", "")
        bkt_display = bkt.get("displayName", "")
        window_raw = bkt.get("window")
        rem_frac = bkt.get("remainingFraction")
        reset_time = bkt.get("resetTime")
        desc = bkt.get("description")

        if rem_frac is None:
          continue

        cadence_suffix, window_sec = _resolve_cadence(bkt_id, bkt_display, window_raw)

        # Standard family prefix
        combined_grp = f"{grp_name} {bkt_id}".lower()
        if "gemini" in combined_grp:
          family = "Gemini"
          win_id = f"gemini_{cadence_suffix}"
        elif any(k in combined_grp for k in ("claude", "gpt", "3p")):
          family = "Claude/GPT"
          win_id = f"claude_gpt_{cadence_suffix}"
        else:
          family = grp_name or "Model"
          win_id = f"{family.lower().replace(' ', '_')}_{cadence_suffix}"

        label = f"{family} {cadence_suffix}"

        windows.append(
          create_window_from_fraction(
            window_id=win_id,
            label=label,
            remaining_fraction=float(rem_frac),
            window_seconds=window_sec if window_sec > 0 else None,
            resets_at=str(reset_time) if reset_time else None,
            reset_description=str(desc) if desc else None,
          )
        )

  return ProviderUsage(
    provider="antigravity",
    account=account,
    source=source,
    windows=windows,
    credits=None,
    spend=None,
    fetched_at=_now_utc(),
    warnings=[],
  )


def normalize_antigravity_user_status_legacy(
  user_status_data: dict[str, Any],
  source: str = "antigravity_agy",
) -> ProviderUsage:
  """Normalize legacy GetUserStatus or GetCommandModelConfigs when RetrieveUserQuotaSummary is unavailable."""
  account = _extract_account(user_status_data)

  user_status = user_status_data.get("userStatus", {})
  configs = user_status.get("cascadeModelConfigData", {}).get("clientModelConfigs", [])

  # Aggregate Gemini vs Claude/GPT models by choosing the lowest remaining quota
  gemini_min_rem: float | None = None
  gemini_reset: str | None = None
  claude_min_rem: float | None = None
  claude_reset: str | None = None

  if isinstance(configs, list):
    for item in configs:
      if not isinstance(item, dict):
        continue
      m_name = str(item.get("modelConfig", {}).get("model", "")).lower()
      q_info = item.get("quotaInfo", {})
      if not isinstance(q_info, dict):
        continue
      rem = q_info.get("remainingFraction")
      res_time = q_info.get("resetTime")
      if rem is None:
        continue

      rem_f = float(rem)
      if "gemini" in m_name:
        if gemini_min_rem is None or rem_f < gemini_min_rem:
          gemini_min_rem = rem_f
          gemini_reset = str(res_time) if res_time else None
      elif any(k in m_name for k in ("claude", "gpt")):
        if claude_min_rem is None or rem_f < claude_min_rem:
          claude_min_rem = rem_f
          claude_reset = str(res_time) if res_time else None

  windows: list[UsageWindow] = []
  if gemini_min_rem is not None:
    windows.append(
      create_window_from_fraction(
        window_id="gemini_legacy",
        label="Gemini",
        remaining_fraction=gemini_min_rem,
        resets_at=gemini_reset,
      )
    )
  if claude_min_rem is not None:
    windows.append(
      create_window_from_fraction(
        window_id="claude_gpt_legacy",
        label="Claude/GPT",
        remaining_fraction=claude_min_rem,
        resets_at=claude_reset,
      )
    )

  return ProviderUsage(
    provider="antigravity",
    account=account,
    source=source,
    windows=windows,
    credits=None,
    spend=None,
    fetched_at=_now_utc(),
    warnings=[],
  )
