"""Discovery and lifecycle management for Antigravity agy process and localhost ports."""

from __future__ import annotations

from contextlib import contextmanager
import subprocess
import sys
import time
from typing import Generator
from ai_usage_monitor.windows.paths import resolve_agy_binary
from ai_usage_monitor.windows.process import find_running_process_pids, get_process_children_pids
from ai_usage_monitor.windows.tcp_table import get_listening_ports_for_pid


def find_existing_agy_listening_ports() -> list[int]:
  """Find listening TCP ports for any already-running agy, antigravity, or language_server processes and their children."""
  pids = set(find_running_process_pids("agy"))
  pids.update(find_running_process_pids("antigravity"))
  pids.update(find_running_process_pids("language_server"))
  all_ports: set[int] = set()

  for pid in pids:
    # Direct process ports
    for port in get_listening_ports_for_pid(pid):
      all_ports.add(port)
    # Child process ports (e.g. language server child)
    child_pids = get_process_children_pids(pid)
    for c_pid in child_pids:
      for port in get_listening_ports_for_pid(c_pid):
        all_ports.add(port)

  return sorted(all_ports)


@contextmanager
def manage_agy_session(
  configured_path: str | None = None,
  startup_timeout: float = 8.0,
) -> Generator[list[int], None, None]:
  """Context manager providing candidate Antigravity localhost ports.

  1. Reuses any already-running agy processes without killing them.
  2. If none running, launches a new owned agy process, polls for listening ports,
     and guarantees clean termination of ONLY the owned child on exit.
  """
  # 1. Check existing running agy
  existing_ports = find_existing_agy_listening_ports()
  if existing_ports:
    yield existing_ports
    return

  # 2. Cold start
  binary = resolve_agy_binary(configured_path)
  if not binary:
    yield []
    return

  proc: subprocess.Popen[bytes] | None = None
  try:
    # Launch agy in non-interactive/background mode without creating a console window
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    proc = subprocess.Popen(
      [binary],
      stdin=subprocess.DEVNULL,
      stdout=subprocess.DEVNULL,
      stderr=subprocess.DEVNULL,
      creationflags=creationflags,
    )

    discovered_ports: list[int] = []
    deadline = time.time() + startup_timeout
    backoffs = [0.2, 0.3, 0.5, 0.75, 1.0]
    backoff_idx = 0

    while time.time() < deadline:
      if proc.poll() is not None:
        # Process exited early
        break

      ports = get_listening_ports_for_pid(proc.pid)
      child_pids = get_process_children_pids(proc.pid)
      for c_pid in child_pids:
        ports.extend(get_listening_ports_for_pid(c_pid))

      if ports:
        discovered_ports = sorted(set(ports))
        break

      sleep_time = backoffs[min(backoff_idx, len(backoffs) - 1)]
      backoff_idx += 1
      time.sleep(sleep_time)

    yield discovered_ports

  finally:
    if proc is not None:
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
