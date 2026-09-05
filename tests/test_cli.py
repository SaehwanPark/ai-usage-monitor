from unittest.mock import MagicMock, patch
import pytest
from ai_usage_monitor.cli import main
from ai_usage_monitor.model import ProviderUsage

def test_cli_doctor(capsys: pytest.CaptureFixture[str]) -> None:
  with patch("ai_usage_monitor.cli.run_doctor", return_value="Mock Doctor"):
    code = main(["doctor"])
    assert code == 0
    captured = capsys.readouterr()
    assert "Mock Doctor" in captured.out

def test_cli_single_provider_success(capsys: pytest.CaptureFixture[str]) -> None:
  mock_usage = ProviderUsage(
    provider="codex",
    account=None,
    source="codex_oauth",
    windows=[],
    credits=None,
    spend=None,
    fetched_at="2026-09-05T22:30:00Z",
    warnings=[],
  )
  with patch("ai_usage_monitor.cli.fetch_codex_usage", return_value=mock_usage):
    code = main(["codex"])
    assert code == 0
    captured = capsys.readouterr()
    assert "Codex" in captured.out

def test_cli_single_provider_json(capsys: pytest.CaptureFixture[str]) -> None:
  mock_usage = ProviderUsage(
    provider="codex",
    account=None,
    source="codex_oauth",
    windows=[],
    credits=None,
    spend=None,
    fetched_at="2026-09-05T22:30:00Z",
    warnings=[],
  )
  with patch("ai_usage_monitor.cli.fetch_codex_usage", return_value=mock_usage):
    code = main(["codex", "--json"])
    assert code == 0
    captured = capsys.readouterr()
    assert '"provider": "codex"' in captured.out

def test_cli_all_partial_success(capsys: pytest.CaptureFixture[str]) -> None:
  success_usage = ProviderUsage(
    provider="codex",
    account=None,
    source="codex_oauth",
    windows=[],
    credits=None,
    spend=None,
    fetched_at="2026-09-05T22:30:00Z",
    warnings=[],
  )
  fail_usage = ProviderUsage(
    provider="cursor",
    account=None,
    source="cursor_auto",
    windows=[],
    credits=None,
    spend=None,
    fetched_at="2026-09-05T22:30:00Z",
    warnings=[],
    error="Token expired",
  )
  with patch("ai_usage_monitor.cli.fetch_codex_usage", return_value=success_usage), \
       patch("ai_usage_monitor.cli.fetch_cursor_usage", return_value=fail_usage), \
       patch("ai_usage_monitor.cli.fetch_antigravity_usage", return_value=success_usage):
    code = main(["all"])
    # Partial success code is 2
    assert code == 2
