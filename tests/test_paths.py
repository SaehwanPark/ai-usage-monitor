import os
from pathlib import Path
from unittest.mock import patch
import pytest
from ai_usage_monitor.paths import (
  get_codex_auth_path,
  get_cursor_cli_auth_path,
  get_cursor_cli_config_path,
  get_cursor_db_path,
  resolve_cursor_binary,
)


def test_get_cursor_db_path_darwin(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.delenv("APPDATA", raising=False)
  with patch("sys.platform", "darwin"):
    path = get_cursor_db_path()
    assert path == Path.home() / "Library" / "Application Support" / "Cursor" / "User" / "globalStorage" / "state.vscdb"


def test_get_cursor_db_path_windows_appdata(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("APPDATA", "C:/Users/tester/AppData/Roaming")
  with patch("sys.platform", "win32"):
    path = get_cursor_db_path()
    assert path == Path("C:/Users/tester/AppData/Roaming/Cursor/User/globalStorage/state.vscdb")


def test_get_cursor_db_path_linux_xdg(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.delenv("APPDATA", raising=False)
  monkeypatch.setenv("XDG_CONFIG_HOME", "/home/tester/.config")
  with patch("sys.platform", "linux"):
    path = get_cursor_db_path()
    assert path == Path("/home/tester/.config/Cursor/User/globalStorage/state.vscdb")


def test_get_cursor_cli_auth_path_darwin() -> None:
  with patch("sys.platform", "darwin"):
    path = get_cursor_cli_auth_path()
    assert path == Path.home() / ".cursor" / "auth.json"


def test_get_cursor_cli_auth_path_windows(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("APPDATA", "C:/Users/tester/AppData/Roaming")
  with patch("sys.platform", "win32"):
    path = get_cursor_cli_auth_path()
    assert path == Path("C:/Users/tester/AppData/Roaming/Cursor/auth.json")


def test_get_cursor_cli_config_path() -> None:
  path = get_cursor_cli_config_path()
  assert path == Path.home() / ".cursor" / "cli-config.json"


def test_resolve_cursor_binary_configured(tmp_path: Path) -> None:
  fake_cursor = tmp_path / "cursor"
  fake_cursor.write_text("echo cursor", encoding="utf-8")
  fake_cursor.chmod(0o755)

  with patch("shutil.which", return_value=str(fake_cursor)):
    resolved = resolve_cursor_binary()
    assert resolved == str(fake_cursor)
