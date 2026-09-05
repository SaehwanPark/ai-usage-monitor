"""OpenAI Codex CLI app-server JSON-RPC fallback fetcher."""

from __future__ import annotations

import json
import subprocess
import time
from typing import Any
from ai_usage_monitor.model import ProviderUsage
from ai_usage_monitor.providers.codex.normalize import normalize_codex_rpc_response
from ai_usage_monitor.windows.paths import resolve_codex_binary


def _read_matching_response(
  proc: subprocess.Popen[str],
  target_id: int,
  timeout_seconds: float,
) -> dict[str, Any]:
  """Read lines from stdout until a response with matching target_id is received."""
  deadline = time.time() + timeout_seconds
  while time.time() < deadline:
    if proc.stdout is None:
      raise RuntimeError("Process stdout pipe is unavailable")
    line = proc.stdout.readline()
    if not line:
      if proc.poll() is not None:
        raise RuntimeError(f"Codex app-server exited prematurely with code {proc.returncode}")
      time.sleep(0.05)
      continue

    line_str = line.strip()
    if not line_str:
      continue

    try:
      data = json.loads(line_str)
      if isinstance(data, dict) and data.get("id") == target_id:
        if "error" in data:
          raise RuntimeError(f"RPC error for request id {target_id}: {data['error']}")
        res = data.get("result", {})
        if isinstance(res, dict):
          return res
        return {}
    except json.JSONDecodeError:
      continue

  raise TimeoutError(f"Timed out waiting for Codex RPC response id {target_id}")


def fetch_codex_rpc_usage(
  codex_bin: str | None = None,
  timeout_seconds: float = 10.0,
) -> ProviderUsage:
  """Fetch usage quota from codex app-server JSON-RPC."""
  binary = codex_bin or resolve_codex_binary()
  if not binary:
    raise FileNotFoundError("Codex CLI executable ('codex' or 'codex.exe') was not found")

  cmd = [binary, "-s", "read-only", "-a", "never", "app-server"]
  proc = subprocess.Popen(
    cmd,
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1,
  )

  account_data: dict[str, Any] = {}
  rate_limits_data: dict[str, Any] = {}

  try:
    if proc.stdin is None:
      raise RuntimeError("Process stdin pipe is unavailable")

    # 1. initialize
    init_req = {
      "id": 1,
      "method": "initialize",
      "params": {"clientInfo": {"name": "ai-usage-monitor", "version": "0.1.0"}},
    }
    proc.stdin.write(json.dumps(init_req) + "\n")
    proc.stdin.flush()
    _read_matching_response(proc, target_id=1, timeout_seconds=min(timeout_seconds, 8.0))

    # 2. initialized notification
    init_notif = {"method": "initialized", "params": {}}
    proc.stdin.write(json.dumps(init_notif) + "\n")
    proc.stdin.flush()

    # 3. account/read
    acct_req = {"id": 2, "method": "account/read", "params": {}}
    proc.stdin.write(json.dumps(acct_req) + "\n")
    proc.stdin.flush()
    account_data = _read_matching_response(proc, target_id=2, timeout_seconds=min(timeout_seconds, 5.0))

    # 4. account/rateLimits/read
    rl_req = {"id": 3, "method": "account/rateLimits/read", "params": {}}
    proc.stdin.write(json.dumps(rl_req) + "\n")
    proc.stdin.flush()
    rate_limits_data = _read_matching_response(proc, target_id=3, timeout_seconds=min(timeout_seconds, 5.0))

  finally:
    # Always cleanly terminate the app-server child process
    try:
      if proc.stdin:
        proc.stdin.close()
    except Exception:
      pass

    try:
      proc.terminate()
      proc.wait(timeout=2.0)
    except Exception:
      try:
        proc.kill()
      except Exception:
        pass

  return normalize_codex_rpc_response(account_data, rate_limits_data)
