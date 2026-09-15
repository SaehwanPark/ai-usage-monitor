import subprocess
from unittest.mock import patch

from ai_usage_monitor.providers.antigravity.provider import fetch_antigravity_usage

CLI_OUTPUT = (
  "Gemini Models\tWeekly Limit Remaining\t38%\t2026-09-18T15:57:30Z\n"
  "Gemini Models\tFive Hour Limit Remaining\t91%\t2026-09-15T02:25:23Z\n"
  "Claude and GPT models\tWeekly Limit Remaining\t68%\t2026-09-20T15:33:05Z\n"
  "Claude and GPT models\tFive Hour Limit Remaining\t100%\t2026-09-15T04:20:49Z"
)


def test_fetch_antigravity_usage_via_cli() -> None:
  completed = subprocess.CompletedProcess(
    args=["agy", "--print", "/usage"],
    returncode=0,
    stdout=CLI_OUTPUT,
    stderr="",
  )

  with patch(
    "ai_usage_monitor.providers.antigravity.provider.resolve_agy_binary",
    return_value="C:/bin/agy.exe",
  ), patch(
    "ai_usage_monitor.providers.antigravity.provider.subprocess.run",
    return_value=completed,
  ) as mock_run:
    usage = fetch_antigravity_usage(timeout_seconds=7.5)

  assert usage.error is None
  assert len(usage.windows) == 4
  assert usage.windows[0].id == "gemini_weekly"
  assert usage.windows[0].used_percent == 62.0
  assert usage.windows[1].id == "gemini_5h"
  assert usage.windows[1].used_percent == 9.0
  assert usage.windows[2].id == "claude_gpt_weekly"
  assert usage.windows[2].used_percent == 32.0
  assert usage.windows[3].id == "claude_gpt_5h"
  assert usage.windows[3].used_percent == 0.0

  mock_run.assert_called_once()
  args, kwargs = mock_run.call_args
  assert args == (["C:/bin/agy.exe", "--print", "/usage"],)
  assert kwargs["stdin"] == subprocess.DEVNULL
  assert kwargs["capture_output"] is True
  assert kwargs["timeout"] == 7.5
  assert kwargs["check"] is False
  assert kwargs.get("shell", False) is False


def test_fetch_antigravity_not_installed() -> None:
  with patch(
    "ai_usage_monitor.providers.antigravity.provider.resolve_agy_binary",
    return_value=None,
  ):
    usage = fetch_antigravity_usage()

  assert usage.error is not None
  assert "not installed" in usage.error.lower()


def test_fetch_antigravity_usage_timeout() -> None:
  timeout = subprocess.TimeoutExpired(cmd="agy", timeout=3.0)
  with patch(
    "ai_usage_monitor.providers.antigravity.provider.resolve_agy_binary",
    return_value="C:/bin/agy.exe",
  ), patch(
    "ai_usage_monitor.providers.antigravity.provider.subprocess.run",
    side_effect=timeout,
  ):
    usage = fetch_antigravity_usage(timeout_seconds=3.0)

  assert usage.error is not None
  assert "timed out" in usage.error.lower()


def test_fetch_antigravity_usage_nonzero_exit() -> None:
  completed = subprocess.CompletedProcess(
    args=["agy", "--print", "/usage"],
    returncode=3,
    stdout="",
    stderr="not logged in",
  )

  with patch(
    "ai_usage_monitor.providers.antigravity.provider.resolve_agy_binary",
    return_value="C:/bin/agy.exe",
  ), patch(
    "ai_usage_monitor.providers.antigravity.provider.subprocess.run",
    return_value=completed,
  ):
    usage = fetch_antigravity_usage()

  assert usage.error is not None
  assert "exited with status 3" in usage.error
  assert "login status" in usage.error
