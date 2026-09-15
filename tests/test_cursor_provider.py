from unittest.mock import MagicMock, patch
import pytest
from ai_usage_monitor.model import ProviderUsage
from ai_usage_monitor.providers.cursor.cli_auth import CursorCliAuth
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


def test_fetch_cursor_usage_cli_token_fallback() -> None:
  mock_claims = CursorTokenClaims(sub="auth0|u2", user_id="u2", exp=9999999999, email="cli@c.com", is_fresh=True)
  mock_cli_auth = CursorCliAuth(access_token="cli.jwt.tok", email="cli@c.com", source_detail="keychain")
  mock_usage = MagicMock(spec=ProviderUsage)

  # Desktop returns None, CLI returns valid credentials
  with patch("ai_usage_monitor.providers.cursor.provider.read_cursor_access_token", return_value=None), \
       patch("ai_usage_monitor.providers.cursor.provider.read_cursor_cli_credentials", return_value=mock_cli_auth), \
       patch("ai_usage_monitor.providers.cursor.provider.parse_cursor_jwt", return_value=mock_claims), \
       patch("ai_usage_monitor.providers.cursor.provider.fetch_cursor_api_data", return_value=({}, {}, None, None)), \
       patch("ai_usage_monitor.providers.cursor.provider.normalize_cursor_usage", return_value=mock_usage):
    res = fetch_cursor_usage()
    assert res == mock_usage


def test_fetch_cursor_usage_explicit_cli_source() -> None:
  mock_claims = CursorTokenClaims(sub="auth0|u2", user_id="u2", exp=9999999999, email="cli@c.com", is_fresh=True)
  mock_cli_auth = CursorCliAuth(access_token="cli.jwt.tok", email="cli@c.com", source_detail="auth_file")
  mock_usage = MagicMock(spec=ProviderUsage)

  with patch("ai_usage_monitor.providers.cursor.provider.read_cursor_access_token") as mock_desktop, \
       patch("ai_usage_monitor.providers.cursor.provider.read_cursor_cli_credentials", return_value=mock_cli_auth), \
       patch("ai_usage_monitor.providers.cursor.provider.parse_cursor_jwt", return_value=mock_claims), \
       patch("ai_usage_monitor.providers.cursor.provider.fetch_cursor_api_data", return_value=({}, {}, None, None)), \
       patch("ai_usage_monitor.providers.cursor.provider.normalize_cursor_usage", return_value=mock_usage):
    res = fetch_cursor_usage(source_preference="cli")
    assert res == mock_usage
    # Desktop discovery should not even be called
    mock_desktop.assert_not_called()


def test_fetch_cursor_usage_explicit_desktop_missing() -> None:
  with patch("ai_usage_monitor.providers.cursor.provider.read_cursor_access_token", return_value=None):
    res = fetch_cursor_usage(source_preference="desktop")
    assert res.error is not None
    assert "desktop credentials not found" in res.error.lower()


def test_fetch_cursor_usage_all_missing() -> None:
  with patch("ai_usage_monitor.providers.cursor.provider.read_cursor_access_token", return_value=None), \
       patch("ai_usage_monitor.providers.cursor.provider.read_cursor_cli_credentials", return_value=None), \
       patch("ai_usage_monitor.providers.cursor.provider.load_config") as mock_cfg:
    mock_cfg.return_value.cursor_cookie = None
    res = fetch_cursor_usage()
    assert res.error is not None
    assert "credentials not found" in res.error.lower()


def test_fetch_cursor_usage_expired_token_no_manual_cookie() -> None:
  mock_claims = CursorTokenClaims(sub="auth0|u1", user_id="u1", exp=100, email="u@c.com", is_fresh=False)

  with patch("ai_usage_monitor.providers.cursor.provider.read_cursor_access_token", return_value="raw.jwt.tok"), \
       patch("ai_usage_monitor.providers.cursor.provider.read_cursor_cli_credentials", return_value=None), \
       patch("ai_usage_monitor.providers.cursor.provider.parse_cursor_jwt", return_value=mock_claims), \
       patch("ai_usage_monitor.providers.cursor.provider.load_config") as mock_cfg:
    mock_cfg.return_value.cursor_cookie = None
    res = fetch_cursor_usage()
    assert res.error is not None
    assert "expired" in res.error.lower()
