"""CLI entrypoint for ai-usage-monitor (usage)."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence
from ai_usage_monitor.config import load_config
from ai_usage_monitor.doctor import run_doctor
from ai_usage_monitor.format import format_provider_human, format_providers_human, format_providers_json
from ai_usage_monitor.model import ProviderUsage
from ai_usage_monitor.providers.antigravity.provider import fetch_antigravity_usage
from ai_usage_monitor.providers.codex.provider import fetch_codex_usage
from ai_usage_monitor.providers.cursor.provider import fetch_cursor_usage


def _classify_error_code(error_msg: str) -> int:
  """Map error message to standard exit code per specification."""
  lower = error_msg.lower()
  if any(k in lower for k in ("auth", "expired", "sign-in", "sign in", "login", "cookie rejected")):
    return 3
  if any(k in lower for k in ("timeout", "network", "unavailable", "connection failed")):
    return 4
  if any(k in lower for k in ("not found", "not installed", "missing")):
    return 5
  return 1


def build_parser() -> argparse.ArgumentParser:
  """Construct command line argument parser."""
  parser = argparse.ArgumentParser(
    prog="usage",
    description="Windows CLI Subscription Usage Monitor for OpenAI Codex, Cursor, and Google Antigravity.",
  )

  parser.add_argument(
    "command",
    nargs="?",
    default="all",
    choices=["all", "codex", "cursor", "antigravity", "doctor"],
    help="Provider to inspect, 'all' for all providers, or 'doctor' for diagnostics (default: all).",
  )

  parser.add_argument(
    "--json",
    action="store_true",
    help="Output results in normalized JSON format.",
  )

  parser.add_argument(
    "--verbose",
    action="store_true",
    help="Enable verbose diagnostic logging (credentials are always redacted).",
  )

  parser.add_argument(
    "--timeout",
    type=float,
    default=None,
    help="Network and process startup timeout in seconds (default: 10.0).",
  )

  parser.add_argument(
    "--cookie",
    type=str,
    default=None,
    help="User-supplied Cursor cookie header override.",
  )

  parser.add_argument(
    "--source",
    type=str,
    default="auto",
    help="Provider source override (e.g. 'oauth', 'cli', 'agy').",
  )

  parser.add_argument(
    "--codex-home",
    type=str,
    default=None,
    help="Override path to CODEX_HOME directory.",
  )

  parser.add_argument(
    "--no-cache",
    action="store_true",
    help="Bypass any caching.",
  )

  return parser


def main(args: Sequence[str] | None = None) -> int:
  """CLI entrypoint function."""
  parser = build_parser()
  parsed = parser.parse_args(args)

  cfg = load_config()
  timeout = parsed.timeout or cfg.timeout_seconds

  cmd = parsed.command.lower()

  if cmd == "doctor":
    report = run_doctor()
    print(report)
    return 0

  if cmd == "codex":
    codex_home = parsed.codex_home or cfg.codex_home
    usage = fetch_codex_usage(
      source_preference=parsed.source,
      codex_home=codex_home,
      timeout_seconds=timeout,
    )
    if parsed.json:
      print(format_providers_json(usage))
    else:
      print(format_provider_human(usage))
    return 0 if usage.error is None else _classify_error_code(usage.error)

  if cmd == "cursor":
    cookie = parsed.cookie or cfg.cursor_cookie
    usage = fetch_cursor_usage(
      cookie_override=cookie,
      timeout_seconds=timeout,
    )
    if parsed.json:
      print(format_providers_json(usage))
    else:
      print(format_provider_human(usage))
    return 0 if usage.error is None else _classify_error_code(usage.error)

  if cmd == "antigravity":
    cli_path = cfg.antigravity_cli
    usage = fetch_antigravity_usage(
      cli_path=cli_path,
      timeout_seconds=timeout,
    )
    if parsed.json:
      print(format_providers_json(usage))
    else:
      print(format_provider_human(usage))
    return 0 if usage.error is None else _classify_error_code(usage.error)

  # "all" command
  codex_home = parsed.codex_home or cfg.codex_home
  cookie = parsed.cookie or cfg.cursor_cookie
  cli_path = cfg.antigravity_cli

  codex_res = fetch_codex_usage(
    source_preference=parsed.source,
    codex_home=codex_home,
    timeout_seconds=timeout,
  )
  cursor_res = fetch_cursor_usage(
    cookie_override=cookie,
    timeout_seconds=timeout,
  )
  antigravity_res = fetch_antigravity_usage(
    cli_path=cli_path,
    timeout_seconds=timeout,
  )

  usages = [codex_res, cursor_res, antigravity_res]

  if parsed.json:
    print(format_providers_json(usages))
  else:
    print(format_providers_human(usages))

  success_count = sum(1 for u in usages if u.error is None)
  if success_count == len(usages):
    return 0
  if success_count > 0:
    return 2  # Partial success
  return 1


if __name__ == "__main__":
  sys.exit(main())
