from ai_usage_monitor.doctor import run_doctor

def test_run_doctor_smoke() -> None:
  report = run_doctor()
  assert "Codex" in report
  assert "Cursor" in report
  assert "Antigravity" in report
