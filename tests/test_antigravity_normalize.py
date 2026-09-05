from ai_usage_monitor.providers.antigravity.normalize import (
  normalize_antigravity_quota_summary,
  normalize_antigravity_user_status_legacy,
)

def test_normalize_antigravity_quota_summary() -> None:
  quota_payload = {
    "response": {
      "groups": [
        {
          "displayName": "Gemini Models",
          "buckets": [
            {
              "bucketId": "gemini-weekly",
              "displayName": "Weekly Limit Remaining",
              "window": "weekly",
              "remainingFraction": 0.85,
              "resetTime": "2026-09-11T15:57:30Z",
              "description": "It will fully refresh in 5 days.",
            },
            {
              "bucketId": "gemini-5h",
              "displayName": "Five Hour Limit Remaining",
              "window": "5h",
              "remainingFraction": 0.60,
              "resetTime": "2026-09-05T23:10:09Z",
              "description": "It will fully refresh in 10 minutes.",
            },
          ],
        },
        {
          "displayName": "Claude and GPT models",
          "buckets": [
            {
              "bucketId": "3p-weekly",
              "displayName": "Weekly Limit Remaining",
              "window": "weekly",
              "remainingFraction": 1.0,
              "resetTime": "2026-09-12T23:08:32Z",
            },
            {
              "bucketId": "3p-5h",
              "displayName": "Five Hour Limit Remaining",
              "window": "5h",
              "remainingFraction": 0.90,
              "resetTime": "2026-09-06T04:08:32Z",
            },
          ],
        },
      ]
    }
  }

  user_status = {
    "userStatus": {
      "email": "user@google.com",
      "userTier": {"name": "Google AI Pro"},
    }
  }

  usage = normalize_antigravity_quota_summary(
    summary_data=quota_payload,
    user_status_data=user_status,
    source="antigravity_agy",
  )

  assert usage.provider == "antigravity"
  assert usage.source == "antigravity_agy"
  assert usage.account is not None
  assert usage.account.email == "user@google.com"
  assert usage.account.plan == "Google AI Pro"
  assert len(usage.windows) == 4

  # Gemini 5h should be 40% used, 60% left
  g5 = next(w for w in usage.windows if w.id == "gemini_5h")
  assert g5.label == "Gemini 5h"
  assert g5.used_percent == 40.0
  assert g5.remaining_percent == 60.0
  assert g5.resets_at == "2026-09-05T23:10:09Z"
  assert g5.reset_description == "It will fully refresh in 10 minutes."

  # Gemini weekly should be 15% used, 85% left
  gw = next(w for w in usage.windows if w.id == "gemini_weekly")
  assert gw.label == "Gemini weekly"
  assert gw.used_percent == 15.0
  assert gw.remaining_percent == 85.0

  # Claude/GPT 5h
  c5 = next(w for w in usage.windows if w.id == "claude_gpt_5h")
  assert c5.label == "Claude/GPT 5h"
  assert c5.used_percent == 10.0
  assert c5.remaining_percent == 90.0

  # Claude/GPT weekly
  cw = next(w for w in usage.windows if w.id == "claude_gpt_weekly")
  assert cw.label == "Claude/GPT weekly"
  assert cw.used_percent == 0.0
  assert cw.remaining_percent == 100.0

def test_normalize_antigravity_user_status_legacy() -> None:
  user_status = {
    "userStatus": {
      "email": "user@google.com",
      "userTier": {"name": "Google AI Pro"},
      "cascadeModelConfigData": {
        "clientModelConfigs": [
          {
            "modelConfig": {"model": "gemini-2.5-pro"},
            "quotaInfo": {"remainingFraction": 0.75, "resetTime": "2026-09-06T00:00:00Z"},
          },
          {
            "modelConfig": {"model": "claude-3-7-sonnet"},
            "quotaInfo": {"remainingFraction": 0.50, "resetTime": "2026-09-06T02:00:00Z"},
          },
        ]
      },
    }
  }

  usage = normalize_antigravity_user_status_legacy(user_status, source="antigravity_agy")
  assert usage.provider == "antigravity"
  assert usage.account is not None
  assert usage.account.email == "user@google.com"
  assert len(usage.windows) == 2

  g_win = next(w for w in usage.windows if "Gemini" in w.label)
  assert g_win.used_percent == 25.0
  assert g_win.remaining_percent == 75.0

  c_win = next(w for w in usage.windows if "Claude" in w.label)
  assert c_win.used_percent == 50.0
  assert c_win.remaining_percent == 50.0


def test_normalize_antigravity_user_status_with_model_id() -> None:
  user_status = {
    "userStatus": {
      "email": "user@google.com",
      "userTier": {"name": "Google AI Pro"},
      "cascadeModelConfigData": {
        "clientModelConfigs": [
          {
            "modelId": "gemini-3.8-flash-high",
            "label": "Gemini 3.8 Flash (High)",
            "modelOrAlias": {"model": "MODEL_PLACEHOLDER_M318"},
            "quotaInfo": {"remainingFraction": 0.80, "resetTime": "2026-09-06T00:00:00Z"},
          },
          {
            "modelId": "claude-sonnet-4-6",
            "label": "Claude Sonnet 4.6 (Thinking)",
            "quotaInfo": {"remainingFraction": 0.90, "resetTime": "2026-09-06T02:00:00Z"},
          },
        ]
      },
    }
  }

  usage = normalize_antigravity_user_status_legacy(user_status, source="antigravity_agy")
  assert usage.provider == "antigravity"
  assert len(usage.windows) == 2

  g_win = next(w for w in usage.windows if "Gemini" in w.label)
  assert g_win.used_percent == 20.0
  assert g_win.remaining_percent == 80.0

  c_win = next(w for w in usage.windows if "Claude" in w.label)
  assert c_win.used_percent == 10.0
  assert c_win.remaining_percent == 90.0
