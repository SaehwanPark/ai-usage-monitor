import base64
import json
import time
from pathlib import Path
from ai_usage_monitor.providers.codex.auth import (
  CodexCredentials,
  decode_jwt_exp,
  is_token_fresh,
  load_codex_credentials,
)

def _make_fake_jwt(exp: int) -> str:
  header = base64.urlsafe_b64encode(b'{"alg":"none"}').decode().rstrip("=")
  payload = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).decode().rstrip("=")
  return f"{header}.{payload}."

def test_decode_jwt_exp() -> None:
  jwt = _make_fake_jwt(1234567890)
  assert decode_jwt_exp(jwt) == 1234567890

def test_is_token_fresh_with_exp() -> None:
  now = 1000.0
  # Expiring in 200 seconds -> stale (< 300s)
  stale_jwt = _make_fake_jwt(1200)
  creds_stale = CodexCredentials(access_token=stale_jwt, account_id="acc-1", last_refresh=None)
  assert is_token_fresh(creds_stale, now_ts=now) is False

  # Expiring in 600 seconds -> fresh (> 300s)
  fresh_jwt = _make_fake_jwt(1600)
  creds_fresh = CodexCredentials(access_token=fresh_jwt, account_id="acc-1", last_refresh=None)
  assert is_token_fresh(creds_fresh, now_ts=now) is True

def test_is_token_fresh_with_last_refresh_fallback() -> None:
  now = time.time()
  opaque_token = "not-a-jwt"
  # Recent refresh (1 hour ago)
  recent = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - 3600))
  creds_recent = CodexCredentials(access_token=opaque_token, account_id="acc-1", last_refresh=recent)
  assert is_token_fresh(creds_recent, now_ts=now) is True

  # 9 days ago -> stale (>= 8 days)
  stale_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - 9 * 86400))
  creds_stale = CodexCredentials(access_token=opaque_token, account_id="acc-1", last_refresh=stale_time)
  assert is_token_fresh(creds_stale, now_ts=now) is False

def test_load_codex_credentials(tmp_path: Path) -> None:
  auth_file = tmp_path / "auth.json"
  auth_file.write_text(
    json.dumps(
      {
        "tokens": {
          "access_token": "token-123",
          "account_id": "account-456",
        },
        "last_refresh": "2026-09-01T12:00:00Z",
      }
    ),
    encoding="utf-8",
  )
  creds = load_codex_credentials(codex_home=str(tmp_path))
  assert creds is not None
  assert creds.access_token == "token-123"
  assert creds.account_id == "account-456"
  assert creds.last_refresh == "2026-09-01T12:00:00Z"
