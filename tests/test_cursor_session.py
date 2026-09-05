import base64
import json
import time
from ai_usage_monitor.providers.cursor.session import (
  derive_session_cookie,
  extract_user_id_from_sub,
  parse_cursor_jwt,
)

def _make_cursor_jwt(sub: str, exp: int, email: str | None = None) -> str:
  header = base64.urlsafe_b64encode(b'{"alg":"none"}').decode().rstrip("=")
  payload_dict: dict[str, object] = {"sub": sub, "exp": exp}
  if email:
    payload_dict["email"] = email
  payload = base64.urlsafe_b64encode(json.dumps(payload_dict).encode()).decode().rstrip("=")
  return f"{header}.{payload}."

def test_extract_user_id_from_sub() -> None:
  assert extract_user_id_from_sub("auth0|user_12345") == "user_12345"
  assert extract_user_id_from_sub("google-oauth2|sub-id.abc") == "sub-id.abc"
  assert extract_user_id_from_sub("simple_id") == "simple_id"
  assert extract_user_id_from_sub("invalid|id with spaces") is None
  assert extract_user_id_from_sub("") is None

def test_parse_cursor_jwt_fresh() -> None:
  now = time.time()
  jwt = _make_cursor_jwt(sub="auth0|user_999", exp=int(now + 300), email="test@cursor.com")
  claims = parse_cursor_jwt(jwt, now_ts=now)
  assert claims is not None
  assert claims.user_id == "user_999"
  assert claims.email == "test@cursor.com"
  assert claims.is_fresh is True

def test_parse_cursor_jwt_expired() -> None:
  now = time.time()
  # Expires in 30 seconds (< 60s safety margin)
  jwt = _make_cursor_jwt(sub="auth0|user_999", exp=int(now + 30))
  claims = parse_cursor_jwt(jwt, now_ts=now)
  assert claims is not None
  assert claims.is_fresh is False

def test_derive_session_cookie() -> None:
  token = "my-token-val"
  cookie = derive_session_cookie("user_123", token)
  assert cookie == "WorkosCursorSessionToken=user_123%3A%3Amy-token-val"
