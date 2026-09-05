"""Windows IP Helper API wrapper to discover listening TCP ports by PID."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import subprocess
import sys

# Win32 Constants
AF_INET = 2
AF_INET6 = 23
TCP_TABLE_OWNER_PID_ALL = 5
MIB_TCP_STATE_LISTEN = 2


class MIB_TCPROW_OWNER_PID(ctypes.Structure):
  _fields_ = [
    ("dwState", wintypes.DWORD),
    ("dwLocalAddr", wintypes.DWORD),
    ("dwLocalPort", wintypes.DWORD),
    ("dwRemoteAddr", wintypes.DWORD),
    ("dwRemotePort", wintypes.DWORD),
    ("dwOwningPid", wintypes.DWORD),
  ]


class MIB_TCP6ROW_OWNER_PID(ctypes.Structure):
  _fields_ = [
    ("ucLocalAddr", ctypes.c_ubyte * 16),
    ("dwLocalScopeId", wintypes.DWORD),
    ("dwLocalPort", wintypes.DWORD),
    ("ucRemoteAddr", ctypes.c_ubyte * 16),
    ("dwRemoteScopeId", wintypes.DWORD),
    ("dwRemotePort", wintypes.DWORD),
    ("dwState", wintypes.DWORD),
    ("dwOwningPid", wintypes.DWORD),
  ]


def _decode_port(raw_port: int) -> int:
  """Convert network-byte-order port integer to host byte order."""
  return ((raw_port & 0xFF) << 8) | ((raw_port >> 8) & 0xFF)


def _get_ports_iphlpapi(target_pid: int) -> list[int]:
  """Query listening ports for target_pid via iphlpapi.GetExtendedTcpTable."""
  if sys.platform != "win32":
    return []

  try:
    iphlpapi = ctypes.WinDLL("iphlpapi.dll")
  except Exception:
    return []

  ports: set[int] = set()

  # IPv4
  try:
    size4 = wintypes.DWORD(0)
    res = iphlpapi.GetExtendedTcpTable(None, ctypes.byref(size4), False, AF_INET, TCP_TABLE_OWNER_PID_ALL, 0)
    buf4 = ctypes.create_string_buffer(size4.value)
    res = iphlpapi.GetExtendedTcpTable(buf4, ctypes.byref(size4), False, AF_INET, TCP_TABLE_OWNER_PID_ALL, 0)
    if res == 0:
      num_entries4 = wintypes.DWORD.from_buffer_copy(buf4, 0).value
      row_size4 = ctypes.sizeof(MIB_TCPROW_OWNER_PID)
      offset4 = 4
      for _ in range(num_entries4):
        row = MIB_TCPROW_OWNER_PID.from_buffer_copy(buf4, offset4)
        offset4 += row_size4
        if row.dwOwningPid == target_pid and row.dwState == MIB_TCP_STATE_LISTEN:
          ports.add(_decode_port(row.dwLocalPort))
  except Exception:
    pass

  # IPv6
  try:
    size6 = wintypes.DWORD(0)
    res = iphlpapi.GetExtendedTcpTable(None, ctypes.byref(size6), False, AF_INET6, TCP_TABLE_OWNER_PID_ALL, 0)
    buf6 = ctypes.create_string_buffer(size6.value)
    res = iphlpapi.GetExtendedTcpTable(buf6, ctypes.byref(size6), False, AF_INET6, TCP_TABLE_OWNER_PID_ALL, 0)
    if res == 0:
      num_entries6 = wintypes.DWORD.from_buffer_copy(buf6, 0).value
      row_size6 = ctypes.sizeof(MIB_TCP6ROW_OWNER_PID)
      offset6 = 4
      for _ in range(num_entries6):
        row6 = MIB_TCP6ROW_OWNER_PID.from_buffer_copy(buf6, offset6)
        offset6 += row_size6
        if row6.dwOwningPid == target_pid and row6.dwState == MIB_TCP_STATE_LISTEN:
          ports.add(_decode_port(row6.dwLocalPort))
  except Exception:
    pass

  return sorted(ports)


def _get_ports_netstat_fallback(target_pid: int) -> list[int]:
  """Fallback port discovery using netstat."""
  ports: set[int] = set()
  try:
    out = subprocess.check_output(["netstat", "-ano", "-p", "tcp"], text=True, errors="replace")
    pid_str = str(target_pid)
    for line in out.splitlines():
      parts = line.split()
      if len(parts) >= 5 and parts[0].upper() == "TCP" and parts[3].upper() == "LISTENING":
        if parts[4] == pid_str:
          addr = parts[1]
          port_str = addr.rsplit(":", 1)[-1]
          try:
            ports.add(int(port_str))
          except ValueError:
            pass
  except Exception:
    pass
  return sorted(ports)


def get_listening_ports_for_pid(target_pid: int) -> list[int]:
  """Return unique listening TCP ports for target_pid."""
  ports = _get_ports_iphlpapi(target_pid)
  if not ports:
    ports = _get_ports_netstat_fallback(target_pid)
  return ports
