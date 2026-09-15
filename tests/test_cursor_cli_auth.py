import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import MagicMock, patch
import pytest
from ai_usage_monitor.providers.cursor.cli_auth import (
  read_cursor_cli_credentials,
  read_cursor_cli_file_tokens,
  read_cursor_cli_user_email,
  read_cursor_keychain_token,
)


def test_read_cursor_keychain_token_success() -> None:
  mock_res = MagicMock(returncode=0, stdout="my-keychain-token\n")
  with patch("sys.platform", "darwin"), \
       patch("subprocess.run", return_value=mock_res):
    token = read_cursor_keychain_token()
    assert token == "my-keychain-token"


def test_read_cursor_keychain_token_failure() -> None:
  mock_res = MagicMock(returncode=1, stdout="")
  with patch("sys.platform", "darwin"), \
       patch("subprocess.run", return_value=mock_res):
    token = read_cursor_keychain_token()
    assert token is None


def test_read_cursor_keychain_token_non_darwin() -> None:
  with patch("sys.platform", "linux"):
    token = read_cursor_keychain_token()
    assert token is None


def test_read_cursor_cli_file_tokens_valid(tmp_path: Path) -> None:
  auth_file = tmp_path / "auth.json"
  auth_file.write_text(
    json.dumps({"accessToken": "tok-123", "refreshToken": "ref-456"}),
    encoding="utf-8",
  )
  access, refresh = read_cursor_cli_file_tokens(auth_file)
  assert access == "tok-123"
  assert refresh == "ref-456"


def test_read_cursor_cli_file_tokens_missing(tmp_path: Path) -> None:
  missing = tmp_path / "nonexistent.json"
  access, refresh = read_cursor_cli_file_tokens(missing)
  assert access is None
  assert refresh is None


def test_read_cursor_cli_file_tokens_malformed(tmp_path: Path) -> None:
  bad_file = tmp_path / "bad.json"
  bad_file.write_text("{not valid json", encoding="utf-8")
  access, refresh = read_cursor_cli_file_tokens(bad_file)
  assert access is None
  assert refresh is None


def test_read_cursor_cli_user_email_valid(tmp_path: Path) -> None:
  config_file = tmp_path / "cli-config.json"
  config_file.write_text(
    json.dumps({"authInfo": {"email": "user@test.org", "userId": "u1"}}),
    encoding="utf-8",
  )
  email = read_cursor_cli_user_email(config_file)
  assert email == "user@test.org"


def test_read_cursor_cli_user_email_missing(tmp_path: Path) -> None:
  missing = tmp_path / "missing.json"
  assert read_cursor_cli_user_email(missing) is None


def test_read_cursor_cli_credentials_keychain_priority(tmp_path: Path) -> None:
  auth_file = tmp_path / "auth.json"
  auth_file.write_text(json.dumps({"accessToken": "file-token"}), encoding="utf-8")

  with patch("sys.platform", "darwin"), \
       patch("ai_usage_monitor.providers.cursor.cli_auth.read_cursor_keychain_token") as mock_kc, \
       patch("ai_usage_monitor.providers.cursor.cli_auth.read_cursor_cli_user_email", return_value="user@mac.com"):
    mock_kc.side_effect = lambda service, account: "kc-access" if service == "cursor-access-token" else "kc-refresh"
    creds = read_cursor_cli_credentials(auth_path=auth_file)
    assert creds is not None
    assert creds.access_token == "kc-access"
    assert creds.refresh_token == "kc-refresh"
    assert creds.email == "user@mac.com"
    assert creds.source_detail == "keychain"


def test_read_cursor_cli_credentials_file_fallback(tmp_path: Path) -> None:
  auth_file = tmp_path / "auth.json"
  auth_file.write_text(
    json.dumps({"accessToken": "file-access", "refreshToken": "file-refresh"}),
    encoding="utf-8",
  )

  with patch("ai_usage_monitor.providers.cursor.cli_auth.read_cursor_keychain_token", return_value=None), \
       patch("ai_usage_monitor.providers.cursor.cli_auth.read_cursor_cli_user_email", return_value="file@user.com"):
    creds = read_cursor_cli_credentials(auth_path=auth_file)
    assert creds is not None
    assert creds.access_token == "file-access"
    assert creds.refresh_token == "file-refresh"
    assert creds.email == "file@user.com"
    assert creds.source_detail == "auth_file"
