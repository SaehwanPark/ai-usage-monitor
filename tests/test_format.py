import json
from ai_usage_monitor.format import format_provider_human, format_providers_human, format_providers_json
from ai_usage_monitor.model import (
  AccountIdentity,
  Credits,
  ProviderUsage,
  Spend,
  UsageWindow,
  create_unknown_window,
  create_window_from_percent,
)

def test_format_provider_human_success() -> None:
  w1 = create_window_from_percent(
    window_id="session",
    label="5-hour",
    used_percent=15.0,
    window_seconds=18000,
    resets_at="2026-09-05T23:00:00Z",
  )
  w2 = create_window_from_percent(
    window_id="weekly",
    label="Weekly",
    used_percent=5.0,
    window_seconds=604800,
    resets_at="2026-09-10T00:00:00Z",
  )
  usage = ProviderUsage(
    provider="codex",
    account=AccountIdentity(id=None, email="user@example.com", plan="plus"),
    source="codex_oauth",
    windows=[w1, w2],
    credits=Credits(has_credits=True, unlimited=False, balance=150.0),
    spend=None,
    fetched_at="2026-09-05T22:30:00Z",
    warnings=[],
  )

  out = format_provider_human(usage)
  assert "Codex" in out
  assert "Plus" in out
  assert "user@example.com" in out
  assert "5-hour" in out
  assert "15% used" in out
  assert "85% left" in out
  assert "Weekly" in out
  assert "5% used" in out
  assert "95% left" in out
  assert "$150.00" in out

def test_format_provider_human_unknown_usage() -> None:
  w = create_unknown_window(window_id="total", label="Total")
  usage = ProviderUsage(
    provider="cursor",
    account=None,
    source="cursor_auto",
    windows=[w],
    credits=None,
    spend=None,
    fetched_at="2026-09-05T22:30:00Z",
    warnings=[],
  )
  out = format_provider_human(usage)
  assert "Cursor" in out
  assert "not available" in out

def test_format_provider_human_error() -> None:
  usage = ProviderUsage(
    provider="cursor",
    account=None,
    source="cursor_auto",
    windows=[],
    credits=None,
    spend=None,
    fetched_at="2026-09-05T22:30:00Z",
    warnings=[],
    error="Token expired",
  )
  out = format_provider_human(usage)
  assert "Cursor" in out
  assert "Token expired" in out

def test_format_providers_json() -> None:
  usage = ProviderUsage(
    provider="codex",
    account=AccountIdentity(id=None, email="user@example.com", plan="plus"),
    source="codex_oauth",
    windows=[],
    credits=None,
    spend=None,
    fetched_at="2026-09-05T22:30:00Z",
    warnings=[],
  )
  json_single = format_providers_json(usage)
  parsed_single = json.loads(json_single)
  assert parsed_single["provider"] == "codex"
  assert parsed_single["account"]["email"] == "user@example.com"

  json_multi = format_providers_json([usage])
  parsed_multi = json.loads(json_multi)
  assert isinstance(parsed_multi, list)
  assert parsed_multi[0]["provider"] == "codex"
