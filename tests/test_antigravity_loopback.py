import pytest
from ai_usage_monitor.providers.antigravity.client import LoopbackSecurityError, post_loopback_json

def test_loopback_security_rejects_external_host() -> None:
  with pytest.raises(LoopbackSecurityError):
    post_loopback_json(
      port=443,
      path="/test",
      payload={},
      host="google.com",
    )

def test_loopback_security_rejects_non_loopback_ip() -> None:
  with pytest.raises(LoopbackSecurityError):
    post_loopback_json(
      port=443,
      path="/test",
      payload={},
      host="192.168.1.1",
    )
