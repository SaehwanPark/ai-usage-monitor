import pytest
from ai_usage_monitor.model import (
  AccountIdentity,
  Credits,
  ProviderUsage,
  Spend,
  UsageWindow,
  clamp,
  create_unknown_window,
  create_window_from_fraction,
  create_window_from_percent,
)

def test_clamp() -> None:
  assert clamp(-5.0, 0.0, 100.0) == 0.0
  assert clamp(50.0, 0.0, 100.0) == 50.0
  assert clamp(150.0, 0.0, 100.0) == 100.0

def test_create_window_from_percent() -> None:
  w = create_window_from_percent(
    window_id="session",
    label="5-hour",
    used_percent=15.0,
    window_seconds=18000,
    resets_at="2026-09-05T23:00:00Z",
  )
  assert w.id == "session"
  assert w.label == "5-hour"
  assert w.used_percent == 15.0
  assert w.remaining_percent == 85.0
  assert w.window_seconds == 18000
  assert w.resets_at == "2026-09-05T23:00:00Z"
  assert w.usage_known is True

def test_create_window_from_fraction() -> None:
  w = create_window_from_fraction(
    window_id="weekly",
    label="Weekly",
    remaining_fraction=0.85,
    window_seconds=604800,
    resets_at="2026-09-12T00:00:00Z",
  )
  assert w.id == "weekly"
  assert w.used_percent == 15.0
  assert w.remaining_percent == 85.0
  assert w.usage_known is True

def test_create_unknown_window() -> None:
  w = create_unknown_window(window_id="session", label="5-hour")
  assert w.usage_known is False
  assert w.used_percent is None
  assert w.remaining_percent is None

def test_provider_usage_to_dict() -> None:
  w1 = create_window_from_percent(
    window_id="session",
    label="5-hour",
    used_percent=15.0,
    window_seconds=18000,
    resets_at="2026-09-05T23:00:00Z",
  )
  usage = ProviderUsage(
    provider="codex",
    account=AccountIdentity(id=None, email="user@example.com", plan="pro"),
    source="codex_oauth",
    windows=[w1],
    credits=Credits(has_credits=True, unlimited=False, balance=150.0),
    spend=None,
    fetched_at="2026-09-05T22:30:00Z",
    warnings=[],
  )
  d = usage.to_dict()
  assert d["provider"] == "codex"
  assert d["account"]["email"] == "user@example.com"
  assert len(d["windows"]) == 1
  assert d["windows"][0]["remaining_percent"] == 85.0
  assert d["credits"]["balance"] == 150.0
