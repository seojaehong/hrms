"""Alertmanager → Telegram forwarding webhook.

Receives Alertmanager v4 webhook POSTs and forwards them to a Telegram chat.

Environment variables
---------------------
TELEGRAM_BOT_TOKEN    required — bot token from BotFather
TELEGRAM_CHAT_ID      required — target chat_id (group or user)
WEBHOOK_PORT          listen port (default: 5001)
WEBHOOK_SECRET        optional shared secret; checked against X-Webhook-Secret header

Mutation boundary: read-only observation only. No Frappe DB access.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

logger = logging.getLogger("alert_webhook")

TELEGRAM_BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.environ.get("TELEGRAM_CHAT_ID", "")
WEBHOOK_PORT: int = int(os.environ.get("WEBHOOK_PORT", "5001"))
WEBHOOK_SECRET: str = os.environ.get("WEBHOOK_SECRET", "")

# ---------------------------------------------------------------------------
# Telegram API helper
# ---------------------------------------------------------------------------

_TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}/sendMessage"
_MAX_MESSAGE_LEN = 4096


def _send_telegram(text: str) -> None:
    """Send a text message to the configured Telegram chat."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set — skipping send")
        return

    url = _TELEGRAM_API_BASE.format(token=TELEGRAM_BOT_TOKEN)
    # Truncate if needed
    if len(text) > _MAX_MESSAGE_LEN:
        text = text[: _MAX_MESSAGE_LEN - 10] + "\n...(truncated)"

    payload = json.dumps(
        {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status != 200:
                logger.error("Telegram API error: %s", resp.read())
    except Exception as exc:
        logger.error("Failed to send Telegram message: %s", exc)


# ---------------------------------------------------------------------------
# Alertmanager payload → human-readable text
# ---------------------------------------------------------------------------

_STATUS_EMOJI = {"firing": "🔴", "resolved": "✅"}
_SEVERITY_EMOJI = {"critical": "🚨", "warning": "⚠️", "info": "ℹ️"}


def _format_alert(alert: dict[str, Any]) -> str:
    labels: dict[str, str] = alert.get("labels", {})
    annotations: dict[str, str] = alert.get("annotations", {})
    status: str = alert.get("status", "unknown")

    emoji = _STATUS_EMOJI.get(status, "❓")
    severity = labels.get("severity", "")
    sev_emoji = _SEVERITY_EMOJI.get(severity, "")

    name = labels.get("alertname", "Unknown")
    summary = annotations.get("summary", "")
    description = annotations.get("description", "")
    instance = labels.get("instance", labels.get("site", ""))

    parts = [f"{emoji} <b>[{status.upper()}]</b> {sev_emoji} <b>{name}</b>"]
    if instance:
        parts.append(f"Instance: <code>{instance}</code>")
    if summary:
        parts.append(f"Summary: {summary}")
    if description:
        parts.append(f"Detail: {description}")
    return "\n".join(parts)


def _format_payload(body: dict[str, Any]) -> str:
    alerts: list[dict[str, Any]] = body.get("alerts", [])
    overall_status: str = body.get("status", "unknown")
    receiver: str = body.get("receiver", "")

    header = f"<b>Frappe HRMS Alert</b> [{overall_status.upper()}]"
    if receiver:
        header += f" — receiver: {receiver}"

    formatted_alerts = [_format_alert(a) for a in alerts]
    return "\n\n".join([header] + formatted_alerts)


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------


class WebhookHandler(BaseHTTPRequestHandler):
    """Minimal HTTP server for Alertmanager webhook (v4 JSON)."""

    server_version = "FrappeAlertWebhook/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: D102
        logger.info(fmt, *args)

    def _send_response(self, code: int, body: str = "") -> None:
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def do_POST(self) -> None:  # noqa: N802
        # Optional secret check
        if WEBHOOK_SECRET:
            incoming = self.headers.get("X-Webhook-Secret", "")
            if incoming != WEBHOOK_SECRET:
                self._send_response(401, "Unauthorized")
                return

        content_length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(content_length)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.error("Invalid JSON payload: %s", exc)
            self._send_response(400, "Bad Request")
            return

        try:
            message = _format_payload(payload)
            _send_telegram(message)
        except Exception as exc:
            logger.exception("Failed to process alert payload: %s", exc)
            self._send_response(500, "Internal Server Error")
            return

        self._send_response(200, "OK")

    def do_GET(self) -> None:  # noqa: N802
        """Health check endpoint."""
        self._send_response(200, "Frappe alert webhook OK")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN environment variable is required")
        raise SystemExit(1)
    if not TELEGRAM_CHAT_ID:
        logger.error("TELEGRAM_CHAT_ID environment variable is required")
        raise SystemExit(1)

    server = HTTPServer(("0.0.0.0", WEBHOOK_PORT), WebhookHandler)
    logger.info("Alert webhook listening on port %d", WEBHOOK_PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down alert webhook")


if __name__ == "__main__":
    main()
