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
from ai_usage_monitor.paths import (
  get_codex_auth_path,
  get_cursor_db_path,
  resolve_agy_binary,
  resolve_codex_binary,
  resolve_cursor_binary,
)
from ai_usage_monitor.providers.cursor.cli_auth import read_cursor_cli_credentials


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
  has_valid_creds = False

  # 1. Desktop check
  db_path = get_cursor_db_path()
  if db_path.is_file():
    lines.append(f"  [ok] desktop state.vscdb found: {db_path}")
    raw_token = read_cursor_access_token(db_path)
    if raw_token:
      lines.append("  [ok] desktop access token present in state.vscdb")
      claims = parse_cursor_jwt(raw_token)
      if claims:
        if claims.is_fresh:
          left_secs = claims.exp - time.time()
          left_h = int(left_secs // 3600)
          left_m = int((left_secs % 3600) // 60)
          lines.append(f"  [ok] desktop token is fresh (expires in {left_h}h {left_m}m)")
          has_valid_creds = True
        else:
          lines.append("  [warn] desktop access token is expired")
          lines.append("         Restart Cursor desktop to refresh.")
      else:
        lines.append("  [fail] desktop access token is malformed")
    else:
      lines.append("  [warn] no access token in desktop state.vscdb")
  else:
    lines.append(f"  [info] desktop state.vscdb not found at: {db_path}")

  # 2. CLI check
  cli_bin = resolve_cursor_binary()
  if cli_bin:
    lines.append(f"  [ok] Cursor CLI binary found: {cli_bin}")
  cli_creds = read_cursor_cli_credentials()
  if cli_creds:
    lines.append(f"  [ok] CLI credentials found ({cli_creds.source_detail})")
    cli_claims = parse_cursor_jwt(cli_creds.access_token)
    if cli_claims:
      if cli_claims.is_fresh:
        left_secs = cli_claims.exp - time.time()
        left_h = int(left_secs // 3600)
        left_m = int((left_secs % 3600) // 60)
        lines.append(f"  [ok] CLI token is fresh (expires in {left_h}h {left_m}m)")
        has_valid_creds = True
      else:
        lines.append("  [warn] CLI access token is expired (run `cursor login` to refresh)")
    else:
      lines.append("  [fail] CLI access token is malformed")
  else:
    lines.append("  [info] CLI credentials not found")

  # 3. Manual cookie check
  if cfg.cursor_cookie:
    lines.append("  [ok] manual Cursor cookie configured")
    has_valid_creds = True

  if not has_valid_creds:
    lines.append("  [fail] no valid Cursor credentials found")
    lines.append("         Log into Cursor desktop, run `cursor login`, or configure LLM_USAGE_CURSOR_COOKIE.")

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
