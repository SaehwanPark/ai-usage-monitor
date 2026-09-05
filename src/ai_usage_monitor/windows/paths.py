"""Windows-specific filesystem path and binary discovery."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess


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
  """Get path to Cursor state database at %APPDATA%\\Cursor\\User\\globalStorage\\state.vscdb."""
  appdata = os.environ.get("APPDATA")
  if appdata:
    return Path(appdata) / "Cursor" / "User" / "globalStorage" / "state.vscdb"
  return Path.home() / "AppData" / "Roaming" / "Cursor" / "User" / "globalStorage" / "state.vscdb"


def resolve_agy_binary(configured_path: str | None = None) -> str | None:
  """Resolve full path to agy executable."""
  if configured_path and Path(configured_path).is_file():
    return configured_path
  found = shutil.which("agy") or shutil.which("agy.exe")
  if found:
    return found
  # Try where.exe
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
  try:
    res = subprocess.run(["where.exe", "codex"], capture_output=True, text=True, check=False)
    if res.returncode == 0:
      lines = [line.strip() for line in res.stdout.splitlines() if line.strip()]
      if lines:
        return lines[0]
  except Exception:
    pass
  return None
