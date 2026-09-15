"""Windows process inspection and discovery utilities."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import subprocess
import sys

TH32CS_SNAPPROCESS = 0x00000002


class PROCESSENTRY32W(ctypes.Structure):
  _fields_ = [
    ("dwSize", wintypes.DWORD),
    ("cntUsage", wintypes.DWORD),
    ("th32ProcessID", wintypes.DWORD),
    ("th32DefaultHeapID", ctypes.c_size_t),
    ("th32ModuleID", wintypes.DWORD),
    ("cntThreads", wintypes.DWORD),
    ("th32ParentProcessID", wintypes.DWORD),
    ("pcPriClassBase", wintypes.LONG),
    ("dwFlags", wintypes.DWORD),
    ("szExeFile", ctypes.c_wchar * 260),
  ]


def _snapshot_processes() -> list[tuple[int, int, str]]:
  """Return a list of (pid, parent_pid, exe_name) for all current processes."""
  if sys.platform != "win32":
    return []

  try:
    kernel32 = ctypes.WinDLL("kernel32.dll")
  except Exception:
    return []

  h_snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
  if h_snapshot == -1 or h_snapshot == 0:
    return []

  entries: list[tuple[int, int, str]] = []
  try:
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
    if kernel32.Process32FirstW(h_snapshot, ctypes.byref(entry)):
      while True:
        entries.append((entry.th32ProcessID, entry.th32ParentProcessID, entry.szExeFile))
        if not kernel32.Process32NextW(h_snapshot, ctypes.byref(entry)):
          break
  finally:
    kernel32.CloseHandle(h_snapshot)

  return entries


def find_running_process_pids(process_name: str) -> list[int]:
  """Find PIDs of processes matching process_name (case-insensitive substring or exact)."""
  name_lower = process_name.lower()
  entries = _snapshot_processes()
  if entries:
    return [
      pid
      for pid, _, exe in entries
      if name_lower in exe.lower() or (name_lower.endswith(".exe") and exe.lower() == name_lower)
    ]

  if sys.platform == "win32":
    # Fallback to tasklist on Windows
    pids: list[int] = []
    try:
      out = subprocess.check_output(["tasklist", "/FO", "CSV", "/NH"], text=True, errors="replace")
      for line in out.splitlines():
        parts = [p.strip('"') for p in line.split(",")]
        if len(parts) >= 2:
          exe, pid_s = parts[0], parts[1]
          if name_lower in exe.lower():
            try:
              pids.append(int(pid_s))
            except ValueError:
              pass
    except Exception:
      pass
    return pids

  # POSIX / macOS fallback using ps
  posix_pids: list[int] = []
  try:
    out = subprocess.check_output(["ps", "-eo", "pid,command"], text=True, errors="replace")
    for line in out.splitlines()[1:]:
      parts = line.strip().split(None, 1)
      if len(parts) == 2:
        pid_s, cmd = parts
        if name_lower in cmd.lower():
          try:
            posix_pids.append(int(pid_s))
          except ValueError:
            pass
  except Exception:
    pass
  return posix_pids


def get_process_children_pids(parent_pid: int) -> list[int]:
  """Return direct and indirect child PIDs for a given parent PID."""
  entries = _snapshot_processes()
  if entries:
    from collections import defaultdict

    tree: dict[int, list[int]] = defaultdict(list)
    for pid, ppid, _ in entries:
      tree[ppid].append(pid)

    result: list[int] = []
    stack = list(tree.get(parent_pid, []))
    while stack:
      curr = stack.pop()
      result.append(curr)
      stack.extend(tree.get(curr, []))

    return result

  if sys.platform != "win32":
    try:
      out = subprocess.check_output(["pgrep", "-P", str(parent_pid)], text=True, errors="replace")
      return [int(p) for p in out.splitlines() if p.strip().isdigit()]
    except Exception:
      return []

  return []


def is_pid_running(pid: int) -> bool:
  """Check if a process with the given PID is currently active."""
  if sys.platform == "win32":
    try:
      kernel32 = ctypes.WinDLL("kernel32.dll")
      # PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
      h_proc = kernel32.OpenProcess(0x1000, False, pid)
      if h_proc:
        exit_code = wintypes.DWORD()
        kernel32.GetExitCodeProcess(h_proc, ctypes.byref(exit_code))
        kernel32.CloseHandle(h_proc)
        # STILL_ACTIVE = 259
        return exit_code.value == 259
      return False
    except Exception:
      return False

  # POSIX / macOS
  import os
  try:
    os.kill(pid, 0)
    return True
  except (OSError, ProcessLookupError):
    return False
