from unittest.mock import MagicMock, patch
import pytest
from ai_usage_monitor.model import ProviderUsage
from ai_usage_monitor.providers.cursor.provider import fetch_cursor_usage
from ai_usage_monitor.providers.cursor.session import CursorTokenClaims

def test_fetch_cursor_usage_manual_cookie_override() -> None:
  mock_usage = MagicMock(spec=ProviderUsage)
  with patch("ai_usage_monitor.providers.cursor.provider.fetch_cursor_api_data", return_value=({}, {}, None, None)), \
       patch("ai_usage_monitor.providers.cursor.provider.normalize_cursor_usage", return_value=mock_usage):
    res = fetch_cursor_usage(cookie_override="WorkosCursorSessionToken=test")
    assert res == mock_usage

def test_fetch_cursor_usage_app_token_success() -> None:
  mock_claims = CursorTokenClaims(sub="auth0|u1", user_id="u1", exp=9999999999, email="u@c.com", is_fresh=True)
  mock_usage = MagicMock(spec=ProviderUsage)

  with patch("ai_usage_monitor.providers.cursor.provider.read_cursor_access_token", return_value="raw.jwt.tok"), \
       patch("ai_usage_monitor.providers.cursor.provider.parse_cursor_jwt", return_value=mock_claims), \
       patch("ai_usage_monitor.providers.cursor.provider.fetch_cursor_api_data", return_value=({}, {}, None, None)), \
       patch("ai_usage_monitor.providers.cursor.provider.normalize_cursor_usage", return_value=mock_usage):
    res = fetch_cursor_usage()
    assert res == mock_usage

def test_fetch_cursor_usage_expired_token_no_manual_cookie() -> None:
  mock_claims = CursorTokenClaims(sub="auth0|u1", user_id="u1", exp=100, email="u@c.com", is_fresh=False)

  with patch("ai_usage_monitor.providers.cursor.provider.read_cursor_access_token", return_value="raw.jwt.tok"), \
       patch("ai_usage_monitor.providers.cursor.provider.parse_cursor_jwt", return_value=mock_claims), \
       patch("ai_usage_monitor.providers.cursor.provider.load_config") as mock_cfg:
    mock_cfg.return_value.cursor_cookie = None
    res = fetch_cursor_usage()
    assert res.error is not None
    assert "expired" in res.error.lower()
