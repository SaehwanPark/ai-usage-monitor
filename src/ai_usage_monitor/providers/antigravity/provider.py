"""Antigravity provider orchestrator."""

from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime

from ai_usage_monitor.config import load_config
from ai_usage_monitor.model import ProviderUsage
from ai_usage_monitor.providers.antigravity.normalize import (
  normalize_antigravity_cli_output,
)
from ai_usage_monitor.windows.paths import resolve_agy_binary


def _now_utc() -> str:
  return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _error_usage(error: str) -> ProviderUsage:
  return ProviderUsage(
    provider="antigravity",
    account=None,
    source="antigravity_agy",
    windows=[],
    credits=None,
    spend=None,
    fetched_at=_now_utc(),
    warnings=[],
    error=error,
  )


def fetch_antigravity_usage(
  cli_path: str | None = None,
  timeout_seconds: float = 10.0,
) -> ProviderUsage:
  """Retrieve current Google Antigravity subscription usage via `agy /usage`."""
  cfg = load_config()
  configured_cli = cli_path or cfg.antigravity_cli

  binary = resolve_agy_binary(configured_cli)
  if not binary:
    return _error_usage(
      "Google Antigravity CLI ('agy') is not installed or not in PATH. Please install agy."
    )

  creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
  try:
    result = subprocess.run(
      [binary, "--print", "/usage"],
      stdin=subprocess.DEVNULL,
      capture_output=True,
      text=True,
      encoding="utf-8",
      errors="replace",
      timeout=timeout_seconds,
      check=False,
      creationflags=creationflags,
    )
  except subprocess.TimeoutExpired:
    return _error_usage(
      f"Antigravity `agy --print /usage` timed out after {timeout_seconds:g} seconds."
    )
  except OSError as exc:
    return _error_usage(f"Failed to run Antigravity CLI: {exc}")

  if result.returncode != 0:
    return _error_usage(
      f"Antigravity `agy --print /usage` exited with status {result.returncode}. "
      "Please verify your agy login status."
    )

  usage = normalize_antigravity_cli_output(result.stdout, source="antigravity_agy")
  if usage.windows:
    return usage

  return _error_usage(
    "Antigravity `agy --print /usage` returned no usable quota. "
    "Please verify your agy login status."
  )
