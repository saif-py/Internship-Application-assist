from __future__ import annotations

from typing import Any

import requests


class WebhookSyncError(RuntimeError):
    """Raised when webhook-based sheet sync fails."""


def sync_rows_via_webhook(
    webhook_url: str,
    webhook_token: str,
    operations: list[dict[str, Any]],
    timeout: int = 45,
) -> dict[str, Any]:
    if not webhook_url:
        raise WebhookSyncError("Missing webhook URL")

    payload = {
        "token": webhook_token,
        "operations": operations,
    }

    try:
        response = requests.post(webhook_url, json=payload, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise WebhookSyncError(f"Webhook request failed: {exc}") from exc

    if not response.content:
        return {"status": "ok", "results": []}

    try:
        parsed = response.json()
    except ValueError:
        raise WebhookSyncError(
            "Webhook returned non-JSON response. Check Apps Script deployment URL and permissions."
        )

    if str(parsed.get("status", "")).lower() != "ok":
        message = parsed.get("message", "unknown error")
        raise WebhookSyncError(f"Webhook sync rejected the request: {message}")

    return parsed
