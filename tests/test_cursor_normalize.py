from ai_usage_monitor.providers.cursor.normalize import normalize_cursor_usage

def test_normalize_cursor_usage_modern_plan() -> None:
  usage_summary = {
    "membershipType": "pro",
    "billingCycleStart": "2026-09-01T00:00:00.000Z",
    "billingCycleEnd": "2026-10-01T00:00:00.000Z",
    "individualUsage": {
      "plan": {
        "totalPercentUsed": 42.5,
        "autoPercentUsed": 31.0,
        "apiPercentUsed": 54.0,
      },
      "onDemand": {
        "used": 738, # 738 cents = $7.38
        "limit": 10000, # 10000 cents = $100.00
      },
    },
  }
  me_data = {"email": "coder@cursor.com", "sub": "auth0|user_123"}
  sand_data = {"usagePercent": 18.0, "nextResetTimestampUtc": "2026-09-09T00:00:00Z"}

  usage = normalize_cursor_usage(
    usage_summary=usage_summary,
    me_data=me_data,
    sand_data=sand_data,
    legacy_data=None,
    source="cursor_app_token",
  )

  assert usage.provider == "cursor"
  assert usage.source == "cursor_app_token"
  assert usage.account is not None
  assert usage.account.email == "coder@cursor.com"
  assert usage.account.plan == "pro"

  # Windows: Total, Cursor, Third Party, Grok Bot
  assert len(usage.windows) == 4

  total_win = usage.windows[0]
  assert total_win.id == "total"
  assert total_win.label == "Total"
  assert total_win.used_percent == 42.5
  assert total_win.remaining_percent == 57.5
  assert total_win.resets_at == "2026-10-01T00:00:00Z"

  cursor_win = usage.windows[1]
  assert cursor_win.label == "Cursor"
  assert cursor_win.used_percent == 31.0

  api_win = usage.windows[2]
  assert api_win.label == "Third Party"
  assert api_win.used_percent == 54.0

  grok_win = usage.windows[3]
  assert grok_win.label == "Grok Bot"
  assert grok_win.used_percent == 18.0
  assert grok_win.remaining_percent == 82.0

  assert usage.spend is not None
  assert usage.spend.used_usd == 7.38
  assert usage.spend.limit_usd == 100.00

def test_normalize_cursor_fractional_percentage_preserved() -> None:
  usage_summary = {
    "individualUsage": {
      "plan": {
        "totalPercentUsed": 0.36, # 0.36% should remain 0.36%
      }
    }
  }
  usage = normalize_cursor_usage(usage_summary=usage_summary, source="cursor_app_token")
  assert usage.windows[0].used_percent == 0.36
  assert usage.windows[0].remaining_percent == 99.64

def test_normalize_cursor_legacy_plan() -> None:
  usage_summary = {
    "membershipType": "pro",
    "individualUsage": {
      "plan": {
        "totalPercentUsed": 50.0,
      }
    },
  }
  legacy_data = {
    "gpt-4": {
      "numRequests": 250,
      "maxRequestUsage": 500,
    }
  }
  usage = normalize_cursor_usage(
    usage_summary=usage_summary,
    legacy_data=legacy_data,
    source="cursor_app_token",
  )
  # Legacy request quota replaces the percentage lanes
  assert len(usage.windows) == 1
  req_win = usage.windows[0]
  assert req_win.label == "Requests"
  assert req_win.used_percent == 50.0
  assert req_win.remaining_percent == 50.0
