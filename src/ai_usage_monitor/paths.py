"""Cross-platform filesystem path and binary discovery."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys


def get_codex_auth_path(codex_home: str | None = None) -> Path:
  """Get path to Codex auth.json according to CODEX_HOME or %USERPROFILE%\\.codex\\auth.json."""
  if codex_home:
    return Path(codex_home) / "auth.json"
  env_home = os.environ.get("CODEX_HOME")
  if env_home:
    return Path(env_home) / "auth.json"
  user_profile = os.environ.get("USERPROFILE")
  if user_profile:
    return Path(user_profile) / ".codex" / "auth.json"
  return Path.home() / ".codex" / "auth.json"


def get_cursor_db_path() -> Path:
  """Get path to Cursor desktop state database (state.vscdb).

  Supports macOS, Windows, and Linux default storage paths.
  """
  appdata = os.environ.get("APPDATA")
  if appdata:
    return Path(appdata) / "Cursor" / "User" / "globalStorage" / "state.vscdb"
  if sys.platform == "darwin":
    return Path.home() / "Library" / "Application Support" / "Cursor" / "User" / "globalStorage" / "state.vscdb"
  if sys.platform == "win32":
    return Path.home() / "AppData" / "Roaming" / "Cursor" / "User" / "globalStorage" / "state.vscdb"

  xdg_config = os.environ.get("XDG_CONFIG_HOME")
  if xdg_config:
    return Path(xdg_config) / "Cursor" / "User" / "globalStorage" / "state.vscdb"
  return Path.home() / ".config" / "Cursor" / "User" / "globalStorage" / "state.vscdb"


def get_cursor_cli_auth_path() -> Path:
  """Get path to Cursor CLI file-based credentials (auth.json)."""
  if sys.platform == "darwin":
    return Path.home() / ".cursor" / "auth.json"
  if sys.platform == "win32":
    appdata = os.environ.get("APPDATA")
    if appdata:
      return Path(appdata) / "Cursor" / "auth.json"
    return Path.home() / "AppData" / "Roaming" / "Cursor" / "auth.json"

  xdg_config = os.environ.get("XDG_CONFIG_HOME")
  if xdg_config:
    return Path(xdg_config) / "cursor" / "auth.json"
  # Check ~/.cursor/auth.json as fallback before ~/.config/cursor/auth.json
  dot_cursor = Path.home() / ".cursor" / "auth.json"
  if dot_cursor.is_file():
    return dot_cursor
  return Path.home() / ".config" / "cursor" / "auth.json"


def get_cursor_cli_config_path() -> Path:
  """Get path to Cursor CLI configuration and cached auth profile (cli-config.json)."""
  return Path.home() / ".cursor" / "cli-config.json"


def resolve_agy_binary(configured_path: str | None = None) -> str | None:
  """Resolve full path to agy executable."""
  if configured_path and Path(configured_path).is_file():
    return configured_path
  found = shutil.which("agy") or shutil.which("agy.exe")
  if found:
    return found
  # Check ~/.local/bin/agy
  local_agy = Path.home() / ".local" / "bin" / "agy"
  if local_agy.is_file() and os.access(local_agy, os.X_OK):
    return str(local_agy)
  # Try where.exe on Windows
  if sys.platform == "win32":
    try:
      res = subprocess.run(["where.exe", "agy"], capture_output=True, text=True, check=False)
      if res.returncode == 0:
        lines = [line.strip() for line in res.stdout.splitlines() if line.strip()]
        if lines:
          return lines[0]
    except Exception:
      pass
  return None


def resolve_codex_binary() -> str | None:
  """Resolve full path to codex executable."""
  found = shutil.which("codex") or shutil.which("codex.exe")
  if found:
    return found
  local_codex = Path.home() / ".local" / "bin" / "codex"
  if local_codex.is_file() and os.access(local_codex, os.X_OK):
    return str(local_codex)
  if sys.platform == "win32":
    try:
      res = subprocess.run(["where.exe", "codex"], capture_output=True, text=True, check=False)
      if res.returncode == 0:
        lines = [line.strip() for line in res.stdout.splitlines() if line.strip()]
        if lines:
          return lines[0]
    except Exception:
      pass
  return None


def resolve_cursor_binary() -> str | None:
  """Resolve full path to cursor or agent CLI executable."""
  for name in ("cursor", "agent", "cursor.exe", "agent.exe"):
    found = shutil.which(name)
    if found:
      return found
  for local_name in ("cursor", "agent"):
    p = Path.home() / ".local" / "bin" / local_name
    if p.is_file() and os.access(p, os.X_OK):
      return str(p)
  return None
