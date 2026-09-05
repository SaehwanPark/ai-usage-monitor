from pathlib import Path
import pytest
from ai_usage_monitor.config import AppConfig, load_config

def test_load_config_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
  monkeypatch.delenv("CODEX_HOME", raising=False)
  monkeypatch.delenv("LLM_USAGE_CURSOR_COOKIE", raising=False)
  monkeypatch.delenv("LLM_USAGE_ANTIGRAVITY_CLI", raising=False)
  monkeypatch.setenv("APPDATA", str(tmp_path))

  cfg = load_config()
  assert cfg.codex_home is None
  assert cfg.cursor_cookie is None
  assert cfg.antigravity_cli is None

def test_load_config_from_toml(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
  config_dir = tmp_path / "llm-usage"
  config_dir.mkdir(parents=True)
  config_file = config_dir / "config.toml"
  config_file.write_text(
    """
    [codex]
    home = "C:/custom/codex"

    [cursor]
    cookie = "WorkosCursorSessionToken=abc"

    [antigravity]
    cli_path = "C:/custom/agy.exe"
    """,
    encoding="utf-8",
  )
  monkeypatch.setenv("APPDATA", str(tmp_path))
  monkeypatch.delenv("CODEX_HOME", raising=False)
  monkeypatch.delenv("LLM_USAGE_CURSOR_COOKIE", raising=False)
  monkeypatch.delenv("LLM_USAGE_ANTIGRAVITY_CLI", raising=False)

  cfg = load_config()
  assert cfg.codex_home == "C:/custom/codex"
  assert cfg.cursor_cookie == "WorkosCursorSessionToken=abc"
  assert cfg.antigravity_cli == "C:/custom/agy.exe"

def test_env_overrides_config_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
  config_dir = tmp_path / "llm-usage"
  config_dir.mkdir(parents=True)
  config_file = config_dir / "config.toml"
  config_file.write_text(
    """
    [cursor]
    cookie = "from_file"
    """,
    encoding="utf-8",
  )
  monkeypatch.setenv("APPDATA", str(tmp_path))
  monkeypatch.setenv("LLM_USAGE_CURSOR_COOKIE", "from_env")

  cfg = load_config()
  assert cfg.cursor_cookie == "from_env"
