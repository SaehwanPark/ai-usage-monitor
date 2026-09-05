from ai_usage_monitor.providers.codex.normalize import (
  normalize_codex_oauth_response,
  normalize_codex_rpc_response,
)

def test_normalize_codex_oauth_response() -> None:
  raw_payload = {
    "plan_type": "plus",
    "email": "user@example.com",
    "rate_limit": {
      "primary_window": {
        "used_percent": 15,
        "limit_window_seconds": 18000,
        "reset_at": 1735401600,
      },
      "secondary_window": {
        "used_percent": 5,
        "limit_window_seconds": 604800,
        "reset_at": 1735920000,
      },
    },
    "credits": {
      "has_credits": True,
      "unlimited": False,
      "balance": "150.00",
    },
    "additional_rate_limits": [
      {
        "limit_name": "GPT-5.3-Codex-Spark",
        "rate_limit": {
          "primary_window": {
            "used_percent": 0,
            "limit_window_seconds": 604800,
            "reset_at": 1735920000,
          },
        },
      }
    ],
  }

  usage = normalize_codex_oauth_response(raw_payload)
  assert usage.provider == "codex"
  assert usage.source == "codex_oauth"
  assert usage.account is not None
  assert usage.account.plan == "plus"
  assert usage.account.email == "user@example.com"
  assert len(usage.windows) == 3

  session_win = usage.windows[0]
  assert session_win.id == "session"
  assert session_win.label == "5-hour"
  assert session_win.used_percent == 15.0
  assert session_win.remaining_percent == 85.0
  assert session_win.window_seconds == 18000
  assert session_win.resets_at is not None

  weekly_win = usage.windows[1]
  assert weekly_win.id == "weekly"
  assert weekly_win.label == "Weekly"
  assert weekly_win.used_percent == 5.0
  assert weekly_win.remaining_percent == 95.0

  spark_win = usage.windows[2]
  assert "GPT-5.3-Codex-Spark" in spark_win.label
  assert spark_win.used_percent == 0.0

  assert usage.credits is not None
  assert usage.credits.has_credits is True
  assert usage.credits.balance == 150.0

def test_normalize_codex_rpc_response() -> None:
  account_data = {
    "account": {
      "type": "chatgpt",
      "email": "user@example.com",
      "planType": "pro",
    }
  }
  rate_limits_data = {
    "rateLimits": {
      "limitId": "codex",
      "primary": {
        "usedPercent": 20,
        "windowDurationMins": 300,
        "resetsAt": 1735401600,
      },
      "secondary": {
        "usedPercent": 10,
        "windowDurationMins": 10080,
        "resetsAt": 1735920000,
      },
      "credits": {
        "hasCredits": True,
        "unlimited": False,
        "balance": 200.0,
      },
    }
  }

  usage = normalize_codex_rpc_response(account_data, rate_limits_data)
  assert usage.provider == "codex"
  assert usage.source == "codex_rpc"
  assert usage.account is not None
  assert usage.account.email == "user@example.com"
  assert usage.account.plan == "pro"
  assert len(usage.windows) == 2

  w1 = usage.windows[0]
  assert w1.id == "session"
  assert w1.label == "5-hour"
  assert w1.used_percent == 20.0
  assert w1.remaining_percent == 80.0
  assert w1.window_seconds == 18000

  w2 = usage.windows[1]
  assert w2.id == "weekly"
  assert w2.label == "Weekly"
  assert w2.used_percent == 10.0
  assert w2.remaining_percent == 90.0
  assert w2.window_seconds == 604800
