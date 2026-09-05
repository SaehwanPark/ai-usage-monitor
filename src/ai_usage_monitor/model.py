"""Core data models and normalization helpers for ai-usage-monitor."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


def clamp(val: float, min_val: float, max_val: float) -> float:
  """Clamp a numeric value between min_val and max_val."""
  return max(min_val, min(val, max_val))


@dataclass(frozen=True)
class AccountIdentity:
  id: str | None = None
  email: str | None = None
  plan: str | None = None


@dataclass(frozen=True)
class UsageWindow:
  id: str
  label: str
  used_percent: float | None
  remaining_percent: float | None
  window_seconds: int | None
  resets_at: str | None
  usage_known: bool
  reset_description: str | None = None


@dataclass(frozen=True)
class Credits:
  has_credits: bool
  unlimited: bool
  balance: float | str | None = None


@dataclass(frozen=True)
class Spend:
  used_usd: float | None
  limit_usd: float | None
  period: str | None = None


@dataclass(frozen=True)
class ProviderUsage:
  provider: str
  account: AccountIdentity | None
  source: str
  windows: list[UsageWindow]
  credits: Credits | None
  spend: Spend | None
  fetched_at: str
  warnings: list[str]
  error: str | None = None

  def to_dict(self) -> dict[str, Any]:
    """Convert ProviderUsage to a clean dictionary representation for JSON output."""
    data = asdict(self)
    # Remove reset_description from public standard schema if null, or keep it
    return data


def create_window_from_percent(
  window_id: str,
  label: str,
  used_percent: float,
  window_seconds: int | None = None,
  resets_at: str | None = None,
  reset_description: str | None = None,
) -> UsageWindow:
  """Create a UsageWindow given a used_percent value (0..100)."""
  clamped_used = round(clamp(used_percent, 0.0, 100.0), 2)
  clamped_remaining = round(clamp(100.0 - clamped_used, 0.0, 100.0), 2)
  return UsageWindow(
    id=window_id,
    label=label,
    used_percent=clamped_used,
    remaining_percent=clamped_remaining,
    window_seconds=window_seconds,
    resets_at=resets_at,
    usage_known=True,
    reset_description=reset_description,
  )


def create_window_from_fraction(
  window_id: str,
  label: str,
  remaining_fraction: float,
  window_seconds: int | None = None,
  resets_at: str | None = None,
  reset_description: str | None = None,
) -> UsageWindow:
  """Create a UsageWindow given a remaining_fraction value (0..1)."""
  clamped_remaining = round(clamp(remaining_fraction * 100.0, 0.0, 100.0), 2)
  clamped_used = round(clamp(100.0 - clamped_remaining, 0.0, 100.0), 2)
  return UsageWindow(
    id=window_id,
    label=label,
    used_percent=clamped_used,
    remaining_percent=clamped_remaining,
    window_seconds=window_seconds,
    resets_at=resets_at,
    usage_known=True,
    reset_description=reset_description,
  )


def create_unknown_window(
  window_id: str,
  label: str,
  window_seconds: int | None = None,
  resets_at: str | None = None,
  reset_description: str | None = None,
) -> UsageWindow:
  """Create a UsageWindow when usage is unknown."""
  return UsageWindow(
    id=window_id,
    label=label,
    used_percent=None,
    remaining_percent=None,
    window_seconds=window_seconds,
    resets_at=resets_at,
    usage_known=False,
    reset_description=reset_description,
  )
