"""Loopback-only TLS client for Antigravity local service."""

from __future__ import annotations

import json
import ssl
from typing import Any
import urllib.parse
import httpx


class LoopbackSecurityError(Exception):
  """Raised when an outbound request attempts to target or redirect to a non-loopback destination."""


def _is_loopback(host: str) -> bool:
  """Check if hostname is strictly local loopback."""
  return host in ("127.0.0.1", "::1", "localhost")


def post_loopback_json(
  port: int,
  path: str,
  payload: dict[str, Any],
  host: str = "127.0.0.1",
  timeout_seconds: float = 3.0,
) -> dict[str, Any]:
  """Send POST request to local Antigravity LanguageServerService endpoint over loopback HTTPS.

  Enforces strict loopback boundaries:
  - Host must be 127.0.0.1 (or ::1 / localhost).
  - Redirects are forbidden.
  - Self-signed SSL validation bypass is strictly scoped to this call only.
  """
  if not _is_loopback(host):
    raise LoopbackSecurityError(f"Security violation: non-loopback host {host} rejected")

  url = f"https://{host}:{port}{path}"

  headers = {
    "Content-Type": "application/json",
    "Connect-Protocol-Version": "1",
  }

  ssl_context = ssl.create_default_context()
  ssl_context.check_hostname = False
  ssl_context.verify_mode = ssl.CERT_NONE

  with httpx.Client(verify=ssl_context, timeout=timeout_seconds, follow_redirects=False) as client:
    try:
      resp = client.post(url, headers=headers, json=payload)
    except httpx.TimeoutException as exc:
      raise TimeoutError(f"Localhost connection to {url} timed out") from exc
    except httpx.RequestError as exc:
      raise ConnectionError(f"Localhost connection to {url} failed: {exc}") from exc

    # Enforce redirect safety
    if 300 <= resp.status_code < 400:
      loc = resp.headers.get("Location")
      if loc:
        parsed = urllib.parse.urlparse(loc)
        if parsed.hostname and not _is_loopback(parsed.hostname):
          raise LoopbackSecurityError(f"Security violation: redirect to non-loopback host {loc} rejected")
      raise RuntimeError(f"Unexpected redirect from localhost endpoint (HTTP {resp.status_code})")

    if resp.status_code != 200:
      raise RuntimeError(f"Localhost endpoint returned HTTP {resp.status_code}")

    try:
      return resp.json()
    except Exception as exc:
      raise ValueError("Invalid JSON response from localhost service") from exc
