from unittest.mock import MagicMock, patch
import pytest
from ai_usage_monitor.model import ProviderUsage
from ai_usage_monitor.providers.antigravity.provider import fetch_antigravity_usage

def test_fetch_antigravity_usage_reusing_running_instance() -> None:
  mock_usage = ProviderUsage(
    provider="antigravity",
    account=None,
    source="antigravity_agy",
    windows=[MagicMock()],
    credits=None,
    spend=None,
    fetched_at="2026-09-05T22:30:00Z",
    warnings=[],
  )

  with patch("ai_usage_monitor.providers.antigravity.provider.resolve_agy_binary", return_value="C:/bin/agy.exe"), \
       patch("ai_usage_monitor.providers.antigravity.discovery.find_running_process_pids", return_value=[12345]), \
       patch("ai_usage_monitor.providers.antigravity.discovery.get_listening_ports_for_pid", return_value=[10687]), \
       patch("ai_usage_monitor.providers.antigravity.provider.post_loopback_json") as mock_post, \
       patch("ai_usage_monitor.providers.antigravity.provider.normalize_antigravity_quota_summary", return_value=mock_usage):

    mock_post.side_effect = [
      # 1st call: RetrieveUserQuotaSummary
      {"response": {"groups": [{"displayName": "Gemini Models", "buckets": []}]}},
      # 2nd call: GetUserStatus
      {"userStatus": {"email": "test@google.com"}},
    ]

    usage = fetch_antigravity_usage()
    assert usage == mock_usage
    assert mock_post.call_count == 2

def test_fetch_antigravity_not_installed() -> None:
  with patch("ai_usage_monitor.providers.antigravity.provider.resolve_agy_binary", return_value=None):
    usage = fetch_antigravity_usage()
    assert usage.error is not None
    assert "not installed" in usage.error.lower()
