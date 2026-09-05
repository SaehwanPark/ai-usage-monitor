"""Diagnostic prerequisite checker ('usage doctor')."""

from __future__ import annotations

import time
from ai_usage_monitor.config import load_config
from ai_usage_monitor.providers.antigravity.client import post_loopback_json
from ai_usage_monitor.providers.antigravity.discovery import find_existing_agy_listening_ports
from ai_usage_monitor.providers.codex.auth import decode_jwt_exp, is_token_fresh, load_codex_credentials
from ai_usage_monitor.providers.cursor.db import read_cursor_access_token
from ai_usage_monitor.providers.cursor.session import parse_cursor_jwt
from ai_usage_monitor.windows.paths import (
  get_codex_auth_path,
  get_cursor_db_path,
  resolve_agy_binary,
  resolve_codex_binary,
)
from ai_usage_monitor.windows.process import find_running_process_pids


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

  pids = find_running_process_pids("agy")
  if pids:
    lines.append(f"  [ok] running agy process detected (PID(s): {', '.join(str(p) for p in pids)})")
  else:
    lines.append("  [info] no running agy process currently active (will launch on demand)")

  ports = find_existing_agy_listening_ports()
  if ports:
    lines.append(f"  [ok] active listening ports detected: {ports}")
    # Probe quota endpoint on first port
    for p in ports:
      try:
        data = post_loopback_json(
          port=p,
          path="/exa.language_server_pb.LanguageServerService/RetrieveUserQuotaSummary",
          payload={"forceRefresh": True},
          timeout_seconds=2.0,
        )
        if data and data.get("response", {}).get("groups"):
          lines.append(f"  [ok] local quota service reachable on port {p}")
          lines.append("  [ok] RetrieveUserQuotaSummary supported")
          break
      except Exception:
        pass

  return lines


def run_doctor() -> str:
  """Run full diagnostic check across Codex, Cursor, and Antigravity."""
  sections = [
    _check_codex(),
    _check_cursor(),
    _check_antigravity(),
  ]
  return "\n\n".join("\n".join(sec) for sec in sections)
