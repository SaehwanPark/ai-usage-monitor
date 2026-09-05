import os
from pathlib import Path
import pytest
from ai_usage_monitor.windows.paths import (
  get_codex_auth_path,
  get_cursor_db_path,
  resolve_agy_binary,
  resolve_codex_binary,
)

def test_get_codex_auth_path_explicit() -> None:
  path = get_codex_auth_path(codex_home="C:/test/codex")
  assert path == Path("C:/test/codex/auth.json")

def test_get_codex_auth_path_env(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("CODEX_HOME", "C:/env/codex")
  path = get_codex_auth_path()
  assert path == Path("C:/env/codex/auth.json")

def test_get_codex_auth_path_userprofile(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.delenv("CODEX_HOME", raising=False)
  monkeypatch.setenv("USERPROFILE", "C:/Users/tester")
  path = get_codex_auth_path()
  assert path == Path("C:/Users/tester/.codex/auth.json")

def test_get_cursor_db_path(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("APPDATA", "C:/Users/tester/AppData/Roaming")
  path = get_cursor_db_path()
  assert path == Path("C:/Users/tester/AppData/Roaming/Cursor/User/globalStorage/state.vscdb")

def test_resolve_agy_binary_configured(tmp_path: Path) -> None:
  fake_agy = tmp_path / "fake_agy.exe"
  fake_agy.write_text("fake", encoding="utf-8")
  resolved = resolve_agy_binary(configured_path=str(fake_agy))
  assert resolved == str(fake_agy)

def test_resolve_binaries_on_current_machine() -> None:
  # On this Windows machine, agy and codex exist!
  agy = resolve_agy_binary()
  assert agy is not None
  assert "agy" in agy.lower()

  codex = resolve_codex_binary()
  assert codex is not None
  assert "codex" in codex.lower()
