from ai_usage_monitor.redact import redact_jwt, redact_secret, redact_headers

def test_redact_secret() -> None:
  assert redact_secret("") == ""
  assert redact_secret(None) == ""
  assert redact_secret("short") == "[REDACTED]"
  # Longer token shows first 3 and last 3 chars
  secret = "abcdefghijklmnop"
  redacted = redact_secret(secret)
  assert "abc" in redacted
  assert "nop" in redacted
  assert "..." in redacted
  assert "defgh" not in redacted

def test_redact_jwt() -> None:
  jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.doNotLeakSignature"
  redacted = redact_jwt(jwt)
  assert "eyJ" in redacted
  assert "doNotLeakSignature" not in redacted

def test_redact_headers() -> None:
  headers = {
    "Authorization": "Bearer super-secret-token",
    "Cookie": "WorkosCursorSessionToken=user::secret-jwt",
    "Accept": "application/json",
  }
  redacted = redact_headers(headers)
  assert redacted["Accept"] == "application/json"
  assert "super-secret-token" not in redacted["Authorization"]
  assert "secret-jwt" not in redacted["Cookie"]
