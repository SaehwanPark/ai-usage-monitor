from unittest.mock import MagicMock, patch
import pytest
from ai_usage_monitor.model import ProviderUsage
from ai_usage_monitor.providers.codex.auth import CodexCredentials
from ai_usage_monitor.providers.codex.provider import fetch_codex_usage

def test_fetch_codex_usage_oauth_success() -> None:
  mock_creds = CodexCredentials(access_token="token", account_id="acc", last_refresh=None)
  mock_usage = MagicMock(spec=ProviderUsage)

  with patch("ai_usage_monitor.providers.codex.provider.load_codex_credentials", return_value=mock_creds), \
       patch("ai_usage_monitor.providers.codex.provider.is_token_fresh", return_value=True), \
       patch("ai_usage_monitor.providers.codex.provider.fetch_codex_oauth_usage", return_value=mock_usage):
    res = fetch_codex_usage(source_preference="auto")
    assert res == mock_usage

def test_fetch_codex_usage_fallback_to_rpc_when_stale() -> None:
  mock_creds = CodexCredentials(access_token="token", account_id="acc", last_refresh=None)
  mock_rpc_usage = MagicMock(spec=ProviderUsage)

  with patch("ai_usage_monitor.providers.codex.provider.load_codex_credentials", return_value=mock_creds), \
       patch("ai_usage_monitor.providers.codex.provider.is_token_fresh", return_value=False), \
       patch("ai_usage_monitor.providers.codex.provider.fetch_codex_rpc_usage", return_value=mock_rpc_usage):
    res = fetch_codex_usage(source_preference="auto")
    assert res == mock_rpc_usage

def test_fetch_codex_usage_missing_everything() -> None:
  with patch("ai_usage_monitor.providers.codex.provider.load_codex_credentials", return_value=None), \
       patch("ai_usage_monitor.providers.codex.provider.resolve_codex_binary", return_value=None):
    res = fetch_codex_usage(source_preference="auto")
    assert res.error is not None
    assert "Codex credentials not found" in res.error or "codex CLI not installed" in res.error
