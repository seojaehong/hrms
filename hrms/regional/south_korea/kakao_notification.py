"""Side-effect-free Kakao Alimtalk notification adapter helpers."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from typing import Any

VARIABLE_RE = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")
RETRYABLE_PROVIDER_STATUSES = {"retryable_error", "rate_limited", "timeout"}
TERMINAL_PROVIDER_STATUSES = {"delivered", "accepted", "permanent_error", "opted_out"}
SUPPORTED_PROVIDER_STATUSES = RETRYABLE_PROVIDER_STATUSES | TERMINAL_PROVIDER_STATUSES
SUPPORTED_PROVIDER_TYPES = {"paid_vendor", "partner_api", "delegated_rpa", "owned_connector"}


def build_kakao_template_payload(
	*,
	recipient_phone: str,
	template_code: str,
	variables: dict[str, Any],
) -> dict[str, Any]:
	"""Build a validated Kakao template payload without sending it."""

	phone = _normalize_phone(recipient_phone)
	if not template_code:
		raise ValueError("template_code is required")
	return {
		"channel": "kakao_alimtalk",
		"recipient_phone": phone,
		"template_code": template_code,
		"variables": {str(key): str(value) for key, value in sorted((variables or {}).items())},
	}


def render_kakao_preview(template: str, variables: dict[str, Any]) -> str:
	"""Render a local preview and reject unresolved template variables."""

	variables = {str(key): str(value) for key, value in (variables or {}).items()}
	missing = sorted({match.group(1) for match in VARIABLE_RE.finditer(template)} - set(variables))
	if missing:
		raise ValueError(f"missing template variables: {', '.join(missing)}")
	return VARIABLE_RE.sub(lambda match: variables[match.group(1)], template)


def build_kakao_send_queue_item(
	*,
	payload: dict[str, Any],
	recipient_consent: bool,
	opted_out: bool = False,
	scheduled_at: str | None = None,
	provider_key: str = "unassigned",
	max_attempts: int = 3,
) -> dict[str, Any]:
	"""Build a side-effect-free Kakao send queue item contract.

	The function does not call a provider or mutate database state. It only
	validates consent/opt-out requirements and returns the queue row shape that a
	later runtime worker can persist and process.
	"""

	payload = _validate_payload(payload)
	if not recipient_consent:
		raise ValueError("recipient_consent is required before queueing Kakao messages")
	if opted_out:
		raise ValueError("recipient has opted out of Kakao notifications")
	if max_attempts < 1:
		raise ValueError("max_attempts must be at least 1")
	if not provider_key:
		raise ValueError("provider_key is required")
	if scheduled_at is not None:
		_parse_iso_datetime(scheduled_at, "scheduled_at")

	return {
		"queue_type": "korea_kakao_send_queue_v1",
		"status": "queued",
		"channel": payload["channel"],
		"provider_key": str(provider_key),
		"dedupe_key": _build_dedupe_key(payload),
		"payload": payload,
		"attempt_count": 0,
		"max_attempts": int(max_attempts),
		"next_attempt_at": scheduled_at,
		"requires_runtime_send": True,
	}


def build_kakao_delivery_audit_event(
	*,
	queue_item: dict[str, Any],
	attempted_at: str,
	provider_status: str,
	provider_message_id: str | None = None,
	error_code: str | None = None,
	base_retry_delay_seconds: int = 60,
	max_retry_delay_seconds: int = 3600,
) -> dict[str, Any]:
	"""Build a provider delivery audit event without mutating the queue item."""

	_validate_queue_item(queue_item)
	attempted_dt = _parse_iso_datetime(attempted_at, "attempted_at")
	if provider_status not in SUPPORTED_PROVIDER_STATUSES:
		raise ValueError(f"provider_status must be one of {sorted(SUPPORTED_PROVIDER_STATUSES)}")
	attempt_number = int(queue_item.get("attempt_count", 0)) + 1
	next_retry_at = None
	if provider_status in RETRYABLE_PROVIDER_STATUSES and attempt_number < int(queue_item["max_attempts"]):
		next_retry_at = _format_iso_datetime(
			attempted_dt
			+ dt.timedelta(
				seconds=_retry_delay_seconds(
					attempt_number,
					base_retry_delay_seconds=base_retry_delay_seconds,
					max_retry_delay_seconds=max_retry_delay_seconds,
				)
			)
		)

	return {
		"event_type": "korea_kakao_delivery_audit_v1",
		"dedupe_key": queue_item["dedupe_key"],
		"provider_key": queue_item["provider_key"],
		"attempt_number": attempt_number,
		"attempted_at": attempted_at,
		"provider_status": provider_status,
		"provider_message_id": provider_message_id,
		"error_code": error_code,
		"next_retry_at": next_retry_at,
	}


def build_kakao_provider_dispatch_request(
	*,
	queue_item: dict[str, Any],
	provider: dict[str, Any],
	requested_at: str,
) -> dict[str, Any]:
	"""Build a provider dispatch request contract without calling the provider.

	The supported provider types reflect practical production routes: paid vendor,
	partner API, delegated/RPA connector, or an owned connector service. Public or
	government API routes are deliberately not accepted here.
	"""

	_validate_queue_item(queue_item)
	_parse_iso_datetime(requested_at, "requested_at")
	provider = _validate_provider(provider, queue_item["provider_key"])
	payload = _validate_payload(queue_item["payload"])
	attempt_number = int(queue_item.get("attempt_count", 0)) + 1

	return {
		"request_type": "korea_kakao_provider_dispatch_v1",
		"runtime_action": "send_via_provider",
		"requires_runtime_send": True,
		"provider_key": provider["provider_key"],
		"provider_type": provider["provider_type"],
		"endpoint_key": provider["endpoint_key"],
		"dispatch_request_id": _build_dispatch_request_id(
			queue_item=queue_item,
			provider=provider,
			attempt_number=attempt_number,
			requested_at=requested_at,
		),
		"dedupe_key": queue_item["dedupe_key"],
		"attempt_number": attempt_number,
		"requested_at": requested_at,
		"payload": payload,
	}


def _normalize_phone(value: str) -> str:
	digits = "".join(ch for ch in str(value or "") if ch.isdigit())
	if not (10 <= len(digits) <= 11) or not digits.startswith("01"):
		raise ValueError("recipient_phone must be a valid Korean mobile number")
	return digits


def _validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
	if not isinstance(payload, dict):
		raise TypeError("payload must be a dict")
	if payload.get("channel") != "kakao_alimtalk":
		raise ValueError("payload.channel must be kakao_alimtalk")
	if not payload.get("recipient_phone"):
		raise ValueError("payload.recipient_phone is required")
	if not payload.get("template_code"):
		raise ValueError("payload.template_code is required")
	return {
		"channel": "kakao_alimtalk",
		"recipient_phone": _normalize_phone(payload["recipient_phone"]),
		"template_code": str(payload["template_code"]),
		"variables": {str(key): str(value) for key, value in sorted((payload.get("variables") or {}).items())},
	}


def _validate_queue_item(queue_item: dict[str, Any]) -> None:
	if not isinstance(queue_item, dict):
		raise TypeError("queue_item must be a dict")
	if queue_item.get("queue_type") != "korea_kakao_send_queue_v1":
		raise ValueError("queue_item.queue_type must be korea_kakao_send_queue_v1")
	for fieldname in ("dedupe_key", "provider_key", "attempt_count", "max_attempts", "payload"):
		if fieldname not in queue_item:
			raise ValueError(f"queue_item.{fieldname} is required")


def _validate_provider(provider: dict[str, Any], expected_provider_key: str) -> dict[str, str]:
	if not isinstance(provider, dict):
		raise TypeError("provider must be a dict")
	provider_key = str(provider.get("provider_key") or "").strip()
	if not provider_key:
		raise ValueError("provider.provider_key is required")
	if provider_key != expected_provider_key:
		raise ValueError("provider.provider_key must match queue_item.provider_key")
	provider_type = str(provider.get("provider_type") or "").strip()
	if provider_type not in SUPPORTED_PROVIDER_TYPES:
		raise ValueError(f"provider_type must be one of {sorted(SUPPORTED_PROVIDER_TYPES)}")
	endpoint_key = str(provider.get("endpoint_key") or "").strip()
	if not endpoint_key:
		raise ValueError("provider.endpoint_key is required")
	return {"provider_key": provider_key, "provider_type": provider_type, "endpoint_key": endpoint_key}


def _build_dedupe_key(payload: dict[str, Any]) -> str:
	body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
	digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
	return f"kakao:{digest}"


def _build_dispatch_request_id(
	*,
	queue_item: dict[str, Any],
	provider: dict[str, str],
	attempt_number: int,
	requested_at: str,
) -> str:
	body = json.dumps(
		{
			"dedupe_key": queue_item["dedupe_key"],
			"provider_key": provider["provider_key"],
			"provider_type": provider["provider_type"],
			"endpoint_key": provider["endpoint_key"],
			"attempt_number": attempt_number,
			"requested_at": requested_at,
		},
		ensure_ascii=False,
		sort_keys=True,
		separators=(",", ":"),
	)
	digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
	return f"kakao-dispatch:{digest}"


def _parse_iso_datetime(value: str, fieldname: str) -> dt.datetime:
	if not isinstance(value, str) or not value:
		raise ValueError(f"{fieldname} must be a non-empty ISO datetime string")
	try:
		parsed = dt.datetime.fromisoformat(value)
	except ValueError as exc:
		raise ValueError(f"{fieldname} must be an ISO datetime string") from exc
	if parsed.tzinfo is None or parsed.utcoffset() is None:
		raise ValueError(f"{fieldname} must include timezone")
	return parsed


def _format_iso_datetime(value: dt.datetime) -> str:
	return value.isoformat()


def _retry_delay_seconds(
	attempt_number: int,
	*,
	base_retry_delay_seconds: int,
	max_retry_delay_seconds: int,
) -> int:
	if base_retry_delay_seconds < 1:
		raise ValueError("base_retry_delay_seconds must be at least 1")
	if max_retry_delay_seconds < base_retry_delay_seconds:
		raise ValueError("max_retry_delay_seconds must be greater than or equal to base_retry_delay_seconds")
	return min(max_retry_delay_seconds, base_retry_delay_seconds * (2 ** max(0, attempt_number - 1)))


__all__ = [
	"build_kakao_template_payload",
	"render_kakao_preview",
	"build_kakao_send_queue_item",
	"build_kakao_delivery_audit_event",
	"build_kakao_provider_dispatch_request",
]
