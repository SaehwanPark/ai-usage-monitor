"""Cursor CLI credential discovery and extraction."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import sys

from ai_usage_monitor.paths import (
  get_cursor_cli_auth_path,
  get_cursor_cli_config_path,
)


@dataclass(frozen=True)
class CursorCliAuth:
  access_token: str
  refresh_token: str | None = None
  email: str | None = None
  source_detail: str = "keychain"


def read_cursor_keychain_token(
  service: str = "cursor-access-token",
  account: str = "cursor-user",
) -> str | None:
  """Read a secret from macOS Keychain using security CLI."""
  if sys.platform != "darwin":
    return None
  try:
    res = subprocess.run(
      ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
      capture_output=True,
      text=True,
      check=False,
      timeout=3.0,
    )
    if res.returncode == 0:
      val = res.stdout.strip()
      return val or None
  except Exception:
    pass
  return None


def read_cursor_cli_file_tokens(
  auth_path: Path | None = None,
) -> tuple[str | None, str | None]:
  """Read accessToken and refreshToken from Cursor CLI auth.json."""
  target = auth_path or get_cursor_cli_auth_path()
  if not target.is_file():
    return None, None
  try:
    data = json.loads(target.read_text(encoding="utf-8"))
    if isinstance(data, dict):
      token = data.get("accessToken")
      refresh = data.get("refreshToken")
      return (
        str(token).strip() if token else None,
        str(refresh).strip() if refresh else None,
      )
  except Exception:
    pass
  return None, None


def read_cursor_cli_user_email(
  config_path: Path | None = None,
) -> str | None:
  """Read cached user email from Cursor CLI cli-config.json."""
  target = config_path or get_cursor_cli_config_path()
  if not target.is_file():
    return None
  try:
    data = json.loads(target.read_text(encoding="utf-8"))
    if isinstance(data, dict):
      auth_info = data.get("authInfo")
      if isinstance(auth_info, dict):
        email = auth_info.get("email")
        if email:
          return str(email).strip()
  except Exception:
    pass
  return None


def read_cursor_cli_credentials(
  auth_path: Path | None = None,
  config_path: Path | None = None,
) -> CursorCliAuth | None:
  """Discover and return Cursor CLI credentials from Keychain or auth file."""
  cached_email = read_cursor_cli_user_email(config_path)

  # 1. On macOS, try Keychain first (default CLI storage)
  if sys.platform == "darwin":
    keychain_access = read_cursor_keychain_token(
      service="cursor-access-token",
      account="cursor-user",
    )
    if keychain_access:
      keychain_refresh = read_cursor_keychain_token(
        service="cursor-refresh-token",
        account="cursor-user",
      )
      return CursorCliAuth(
        access_token=keychain_access,
        refresh_token=keychain_refresh,
        email=cached_email,
        source_detail="keychain",
      )

  # 2. Try file-based storage (AGENT_CLI_CREDENTIAL_STORE=file, Linux, Windows, or fallback)
  file_access, file_refresh = read_cursor_cli_file_tokens(auth_path)
  if file_access:
    return CursorCliAuth(
      access_token=file_access,
      refresh_token=file_refresh,
      email=cached_email,
      source_detail="auth_file",
    )

  return None
