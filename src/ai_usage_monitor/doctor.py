"""Diagnostic prerequisite checker ('usage doctor')."""

from __future__ import annotations

import time

from ai_usage_monitor.config import load_config
from ai_usage_monitor.providers.antigravity.provider import fetch_antigravity_usage
from ai_usage_monitor.providers.codex.auth import (
  decode_jwt_exp,
  is_token_fresh,
  load_codex_credentials,
)
from ai_usage_monitor.providers.cursor.db import read_cursor_access_token
from ai_usage_monitor.providers.cursor.session import parse_cursor_jwt
from ai_usage_monitor.windows.paths import (
  get_codex_auth_path,
  get_cursor_db_path,
  resolve_agy_binary,
  resolve_codex_binary,
)


def _check_codex() -> list[str]:
  lines = ["Codex"]
  cfg = load_config()
  codex_bin = resolve_codex_binary()
  if codex_bin:
    lines.append(f"  [ok] codex binary found: {codex_bin}")
  else:
    lines.append("  [warn] codex binary not found on PATH (CLI RPC fallback unavailable)")

  auth_path = get_codex_auth_path(cfg.codex_home)
  if auth_path.is_file():
    lines.append(f"  [ok] auth file found: {auth_path}")
  else:
    lines.append(f"  [fail] auth file missing at: {auth_path}")
    lines.append("         Run `codex` interactively to sign in.")
    return lines

  creds = load_codex_credentials(cfg.codex_home)
  if not creds:
    lines.append("  [fail] no valid access token found in auth.json")
    return lines

  lines.append("  [ok] OAuth access token present")
  if is_token_fresh(creds):
    exp = decode_jwt_exp(creds.access_token)
    if exp:
      left_secs = exp - time.time()
      left_h = int(left_secs // 3600)
      left_m = int((left_secs % 3600) // 60)
      lines.append(f"  [ok] token is fresh (expires in {left_h}h {left_m}m)")
    else:
      lines.append("  [ok] token is fresh (based on recent refresh)")
  else:
    lines.append("  [warn] access token is stale; will require CLI RPC refresh")

  return lines


def _check_cursor() -> list[str]:
  lines = ["Cursor"]
  cfg = load_config()
  db_path = get_cursor_db_path()

  if db_path.is_file():
    lines.append(f"  [ok] state.vscdb found: {db_path}")
  else:
    lines.append(f"  [warn] state.vscdb not found at: {db_path}")

  raw_token = read_cursor_access_token(db_path)
  if raw_token:
    lines.append("  [ok] cursorAuth/accessToken found in SQLite database")
    claims = parse_cursor_jwt(raw_token)
    if claims:
      if claims.is_fresh:
        left_secs = claims.exp - time.time()
        left_h = int(left_secs // 3600)
        left_m = int((left_secs % 3600) // 60)
        lines.append(f"  [ok] token is fresh (expires in {left_h}h {left_m}m)")
      else:
        lines.append("  [fail] desktop access token is expired")
        lines.append("         Focus/restart Cursor desktop to refresh, or configure a manual cookie.")
    else:
      lines.append("  [fail] token is malformed")
  else:
    lines.append("  [warn] no access token in state.vscdb")

  if cfg.cursor_cookie:
    lines.append("  [ok] manual Cursor cookie configured")

  return lines


def _check_antigravity() -> list[str]:
  lines = ["Antigravity"]
  cfg = load_config()
  agy_bin = resolve_agy_binary(cfg.antigravity_cli)

  if agy_bin:
    lines.append(f"  [ok] agy found: {agy_bin}")
  else:
    lines.append("  [fail] agy binary not found on PATH")
    lines.append("         Install Google Antigravity CLI and ensure 'agy' is on PATH.")
    return lines

  usage = fetch_antigravity_usage(
    cli_path=cfg.antigravity_cli,
    timeout_seconds=cfg.timeout_seconds,
  )
  if usage.error:
    lines.append(f"  [fail] `agy --print /usage` failed: {usage.error}")
  else:
    lines.append("  [ok] `agy --print /usage` returned quota")

  return lines


def run_doctor() -> str:
  """Run full diagnostic check across Codex, Cursor, and Antigravity."""
  sections = [
    _check_codex(),
    _check_cursor(),
    _check_antigravity(),
  ]
  return "\n\n".join("\n".join(sec) for sec in sections)
