"""Configuration handling for ai-usage-monitor."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import tomllib


@dataclass(frozen=True)
class AppConfig:
  codex_home: str | None = None
  cursor_cookie: str | None = None
  antigravity_cli: str | None = None
  timeout_seconds: float = 10.0


def default_config_path() -> Path:
  """Get default path to config.toml in %APPDATA%\\llm-usage\\config.toml."""
  appdata = os.environ.get("APPDATA")
  if appdata:
    return Path(appdata) / "llm-usage" / "config.toml"
  return Path.home() / ".config" / "llm-usage" / "config.toml"


def load_config(custom_path: Path | None = None) -> AppConfig:
  """Load configuration from config.toml and environment variable overrides."""
  cfg_path = custom_path or default_config_path()

  file_codex_home: str | None = None
  file_cursor_cookie: str | None = None
  file_antigravity_cli: str | None = None
  file_timeout: float = 10.0

  if cfg_path.is_file():
    try:
      with cfg_path.open("rb") as f:
        data = tomllib.load(f)
      codex_sec = data.get("codex", {})
      cursor_sec = data.get("cursor", {})
      antigravity_sec = data.get("antigravity", {})
      general_sec = data.get("general", {})

      file_codex_home = codex_sec.get("home")
      file_cursor_cookie = cursor_sec.get("cookie")
      file_antigravity_cli = antigravity_sec.get("cli_path")
      file_timeout = float(general_sec.get("timeout", 10.0))
    except Exception:
      pass

  # Env overrides
  env_codex_home = os.environ.get("CODEX_HOME")
  env_cursor_cookie = os.environ.get("LLM_USAGE_CURSOR_COOKIE")
  env_antigravity_cli = os.environ.get("LLM_USAGE_ANTIGRAVITY_CLI")
  env_timeout_str = os.environ.get("LLM_USAGE_TIMEOUT")

  final_codex_home = env_codex_home or file_codex_home
  final_cursor_cookie = env_cursor_cookie or file_cursor_cookie
  final_antigravity_cli = env_antigravity_cli or file_antigravity_cli

  final_timeout = file_timeout
  if env_timeout_str:
    try:
      final_timeout = float(env_timeout_str)
    except ValueError:
      pass

  return AppConfig(
    codex_home=final_codex_home,
    cursor_cookie=final_cursor_cookie,
    antigravity_cli=final_antigravity_cli,
    timeout_seconds=final_timeout,
  )
