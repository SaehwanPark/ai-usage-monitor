"""OpenAI Codex OAuth usage fetcher."""

from __future__ import annotations

from typing import Any
import httpx
from ai_usage_monitor.model import AccountIdentity, ProviderUsage
from ai_usage_monitor.providers.codex.auth import CodexCredentials
from ai_usage_monitor.providers.codex.normalize import normalize_codex_oauth_response


class CodexAuthError(Exception):
  """Raised when Codex OAuth authentication fails (401 or 403)."""


def fetch_codex_oauth_usage(credentials: CodexCredentials, timeout_seconds: float = 10.0) -> ProviderUsage:
  """Fetch usage quota from https://chatgpt.com/backend-api/wham/usage using OAuth access token."""
  headers = {
    "Authorization": f"Bearer {credentials.access_token}",
    "User-Agent": "codex-cli",
    "Accept": "application/json",
  }
  if credentials.account_id:
    headers["ChatGPT-Account-Id"] = credentials.account_id

  url = "https://chatgpt.com/backend-api/wham/usage"

  with httpx.Client(timeout=timeout_seconds) as client:
    try:
      resp = client.get(url, headers=headers)
    except httpx.TimeoutException as exc:
      raise TimeoutError(f"Request to Codex usage endpoint timed out after {timeout_seconds}s") from exc
    except httpx.RequestError as exc:
      raise ConnectionError(f"Network error contacting Codex usage endpoint: {exc}") from exc

    if resp.status_code in (401, 403):
      raise CodexAuthError(f"Codex access token expired or invalid (HTTP {resp.status_code})")

    if resp.status_code != 200:
      raise RuntimeError(f"Codex usage endpoint returned HTTP {resp.status_code}")

    try:
      body: dict[str, Any] = resp.json()
    except Exception as exc:
      raise ValueError("Invalid JSON received from Codex usage endpoint") from exc

  usage = normalize_codex_oauth_response(body)
  # If email wasn't returned in the response body, use email from JWT/tokens if available
  if (not usage.account or not usage.account.email) and credentials.email:
    acct = AccountIdentity(
      id=usage.account.id if usage.account else None,
      email=credentials.email,
      plan=usage.account.plan if usage.account else None,
    )
    usage = ProviderUsage(
      provider=usage.provider,
      account=acct,
      source=usage.source,
      windows=usage.windows,
      credits=usage.credits,
      spend=usage.spend,
      fetched_at=usage.fetched_at,
      warnings=usage.warnings,
    )

  return usage
