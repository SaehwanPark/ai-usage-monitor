import os
from ai_usage_monitor.windows.process import (
  find_running_process_pids,
  get_process_children_pids,
  is_pid_running,
)

def test_is_pid_running_current() -> None:
  assert is_pid_running(os.getpid()) is True

def test_is_pid_running_invalid() -> None:
  assert is_pid_running(99999999) is False

def test_find_running_process_pids_python() -> None:
  pids = find_running_process_pids("python")
  assert len(pids) > 0
  assert os.getpid() in pids

def test_get_process_children_pids() -> None:
  # Just verify it returns a list without error
  children = get_process_children_pids(os.getpid())
  assert isinstance(children, list)
