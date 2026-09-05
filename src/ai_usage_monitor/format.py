"""Human-readable and JSON formatting for provider usage data."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Sequence
from ai_usage_monitor.model import ProviderUsage, UsageWindow


def _format_reset_time(resets_at: str | None, reset_desc: str | None = None) -> str:
  """Format reset timestamp into human-readable relative duration and local time."""
  if reset_desc:
    # If a rich prose description exists, format it compactly
    cleaned_desc = reset_desc.strip()
    if cleaned_desc.startswith("You have used some of your"):
      # Extract "it will fully refresh in..."
      idx = cleaned_desc.find("it will fully refresh in")
      if idx != -1:
        cleaned_desc = "resets in " + cleaned_desc[idx + len("it will fully refresh in ") :].rstrip(".")
    if resets_at:
      try:
        dt = datetime.fromisoformat(resets_at.replace("Z", "+00:00")).astimezone()
        local_str = dt.strftime("%b %d %I:%M %p")
        return f"{cleaned_desc} ({local_str})"
      except Exception:
        pass
    return cleaned_desc

  if not resets_at:
    return ""

  try:
    utc_dt = datetime.fromisoformat(resets_at.replace("Z", "+00:00")).astimezone(timezone.utc)
    now = datetime.now(timezone.utc)
    delta = utc_dt - now

    local_dt = utc_dt.astimezone()
    local_str = local_dt.strftime("%b %d %I:%M %p")

    secs = delta.total_seconds()
    if secs <= 0:
      return f"resets now ({local_str})"

    days = int(secs // 86400)
    hours = int((secs % 86400) // 3600)
    mins = int((secs % 3600) // 60)

    if days > 0:
      rel = f"{days}d {hours}h"
    elif hours > 0:
      rel = f"{hours}h {mins}m"
    elif mins > 0:
      rel = f"{mins}m"
    else:
      rel = "< 1m"

    return f"resets in {rel} ({local_str})"
  except Exception:
    return f"resets {resets_at}"


def _format_percent(val: float | None) -> str:
  """Format a percentage cleanly without trailing zeros if integer."""
  if val is None:
    return "--%"
  if val == int(val):
    return f"{int(val)}%"
  return f"{val:.1f}%"


def _format_window_line(window: UsageWindow) -> str:
  """Format a single usage window line."""
  label = window.label
  if not window.usage_known or window.used_percent is None:
    return f"  {label:<15} Limits not available from current source"

  used_str = _format_percent(window.used_percent)
  left_str = _format_percent(window.remaining_percent)
  reset_info = _format_reset_time(window.resets_at, window.reset_description)

  return f"  {label:<15} {used_str:>6} used  {left_str:>6} left  {reset_info}".rstrip()


def format_provider_human(usage: ProviderUsage) -> str:
  """Format a single ProviderUsage into a human-readable block."""
  title = usage.provider.capitalize()
  if title.lower() == "codex":
    title = "Codex"
  elif title.lower() == "cursor":
    title = "Cursor"
  elif title.lower() == "antigravity":
    title = "Antigravity"

  header_parts = [title]
  if usage.account:
    if usage.account.plan:
      header_parts.append(usage.account.plan.capitalize())
    if usage.account.email:
      header_parts.append(usage.account.email)

  if usage.source:
    header_parts.append(f"({usage.source})")

  lines = ["  ".join(header_parts)]

  if usage.error:
    lines.append(f"  Error: {usage.error}")
    return "\n".join(lines)

  if not usage.windows:
    lines.append("  No quota windows available.")

  for w in usage.windows:
    lines.append(_format_window_line(w))

  if usage.credits and usage.credits.has_credits and usage.credits.balance is not None:
    try:
      bal_float = float(usage.credits.balance)
      lines.append(f"  {'Credits':<15} ${bal_float:.2f}")
    except (ValueError, TypeError):
      lines.append(f"  {'Credits':<15} {usage.credits.balance}")

  if usage.spend and (usage.spend.used_usd is not None or usage.spend.limit_usd is not None):
    used_s = f"${usage.spend.used_usd:.2f}" if usage.spend.used_usd is not None else "$0.00"
    limit_s = f"${usage.spend.limit_usd:.2f}" if usage.spend.limit_usd is not None else "Unlimited"
    lines.append(f"  {'On-demand':<15} {used_s} / {limit_s}")

  for warn in usage.warnings:
    lines.append(f"  Warning: {warn}")

  return "\n".join(lines)


def format_providers_human(usages: Sequence[ProviderUsage]) -> str:
  """Format multiple ProviderUsage results separated by blank lines."""
  return "\n\n".join(format_provider_human(u) for u in usages)


def format_providers_json(usages: ProviderUsage | Sequence[ProviderUsage]) -> str:
  """Serialize one or multiple ProviderUsage instances to JSON."""
  if isinstance(usages, ProviderUsage):
    return json.dumps(usages.to_dict(), indent=2)
  return json.dumps([u.to_dict() for u in usages], indent=2)
