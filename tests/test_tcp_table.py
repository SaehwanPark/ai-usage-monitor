import os
from ai_usage_monitor.windows.tcp_table import get_listening_ports_for_pid

def test_get_listening_ports_for_invalid_pid() -> None:
  # PID 99999999 is unlikely to exist and listen
  ports = get_listening_ports_for_pid(99999999)
  assert ports == []

def test_get_listening_ports_for_current_or_running_pid() -> None:
  # Verify the function runs without error on current pid
  my_pid = os.getpid()
  ports = get_listening_ports_for_pid(my_pid)
  assert isinstance(ports, list)
