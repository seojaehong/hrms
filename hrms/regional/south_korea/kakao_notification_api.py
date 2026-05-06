"""Frappe-facing preview API for Korea Kakao notification contracts.

This module is intentionally preview-only. It normalizes JSON/dict inputs and
returns side-effect-free queue/dispatch contracts without saving queue rows,
calling Kakao providers, or assuming public/government API routes. Direct file
tests can run without a bench; when Frappe is present the functions are
whitelisted.
"""

from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

try:  # pragma: no cover - exercised only inside a Frappe bench
	import frappe  # type: ignore
except ImportError:  # pragma: no cover - direct-run no-bench mode
	frappe = None  # type: ignore


def _whitelist(fn):
	if frappe is None:
		return fn
	return frappe.whitelist()(fn)


@_whitelist
def preview_korea_kakao_template_registry_entry(
	*,
	template_code: str,
	template_name: str,
	template_body: str,
	required_variables: Any,
	consent_purpose: str,
	provider_template_keys: Any | None = None,
	active: bool | str = True,
) -> dict[str, Any]:
	"""Return a side-effect-free Kakao approved-template registry preview."""

	kakao = _load_sibling_module("kakao_notification.py", "korea_kakao_notification")
	registry_entry = kakao.build_kakao_template_registry_entry(
		template_code=template_code,
		template_name=template_name,
		template_body=template_body,
		required_variables=_coerce_list(required_variables, "required_variables"),
		consent_purpose=consent_purpose,
		provider_template_keys=_coerce_optional_mapping(provider_template_keys, "provider_template_keys"),
		active=_coerce_bool(active, "active"),
	)
	return {
		"contract_type": "korea_kakao_template_registry_preview_v1",
		"runtime_action": "preview_only",
		"requires_runtime_send": False,
		"registry_entry": deepcopy(registry_entry),
	}


@_whitelist
def preview_korea_kakao_registered_queue_item(
	*,
	recipient_phone: str,
	template_registry_entry: Any,
	variables: Any,
	recipient_consent: bool,
	opted_out: bool = False,
	scheduled_at: str | None = None,
	provider_key: str = "unassigned",
	max_attempts: int | str = 3,
) -> dict[str, Any]:
	"""Return a side-effect-free Kakao registered-template queue preview."""

	kakao = _load_sibling_module("kakao_notification.py", "korea_kakao_notification")
	payload = kakao.build_registered_kakao_template_payload(
		recipient_phone=recipient_phone,
		template_registry_entry=_coerce_mapping(template_registry_entry, "template_registry_entry"),
		variables=_coerce_mapping(variables, "variables"),
	)
	queue_item = kakao.build_kakao_send_queue_item(
		payload=payload,
		recipient_consent=_coerce_bool(recipient_consent, "recipient_consent"),
		opted_out=_coerce_bool(opted_out, "opted_out"),
		scheduled_at=scheduled_at,
		provider_key=provider_key,
		max_attempts=_coerce_int(max_attempts, "max_attempts"),
	)
	return {
		"contract_type": "korea_kakao_queue_preview_v1",
		"runtime_action": "preview_only",
		"requires_runtime_send": True,
		"payload": deepcopy(payload),
		"queue_item": deepcopy(queue_item),
	}


@_whitelist
def preview_korea_kakao_provider_dispatch(*, queue_item: Any, provider: Any, requested_at: str) -> dict[str, Any]:
	"""Return a side-effect-free Kakao provider dispatch request preview."""

	kakao = _load_sibling_module("kakao_notification.py", "korea_kakao_notification")
	dispatch_request = kakao.build_kakao_provider_dispatch_request(
		queue_item=_coerce_mapping(queue_item, "queue_item"),
		provider=_coerce_mapping(provider, "provider"),
		requested_at=requested_at,
	)
	return {
		"contract_type": "korea_kakao_dispatch_preview_v1",
		"runtime_action": "preview_only",
		"requires_runtime_send": True,
		"dispatch_request": deepcopy(dispatch_request),
	}


@_whitelist
def preview_korea_kakao_delivery_audit_event(
	*,
	queue_item: Any,
	attempted_at: str,
	provider_status: str,
	provider_message_id: str | None = None,
	error_code: str | None = None,
	base_retry_delay_seconds: int | str = 60,
	max_retry_delay_seconds: int | str = 3600,
) -> dict[str, Any]:
	"""Return a side-effect-free Kakao delivery audit event preview."""

	kakao = _load_sibling_module("kakao_notification.py", "korea_kakao_notification")
	audit_event = kakao.build_kakao_delivery_audit_event(
		queue_item=_coerce_mapping(queue_item, "queue_item"),
		attempted_at=attempted_at,
		provider_status=provider_status,
		provider_message_id=provider_message_id,
		error_code=error_code,
		base_retry_delay_seconds=_coerce_int(base_retry_delay_seconds, "base_retry_delay_seconds"),
		max_retry_delay_seconds=_coerce_int(max_retry_delay_seconds, "max_retry_delay_seconds"),
	)
	return {
		"contract_type": "korea_kakao_delivery_audit_preview_v1",
		"runtime_action": "preview_only",
		"requires_runtime_send": True,
		"audit_event": deepcopy(audit_event),
	}


def _coerce_mapping(value: Any, fieldname: str) -> dict[str, Any]:
	coerced = _coerce_json_if_needed(value)
	if not isinstance(coerced, dict):
		raise ValueError(f"{fieldname} must be a dict or JSON object")
	return coerced


def _coerce_optional_mapping(value: Any | None, fieldname: str) -> dict[str, Any]:
	if value is None:
		return {}
	return _coerce_mapping(value, fieldname)


def _coerce_list(value: Any, fieldname: str) -> list[Any]:
	coerced = _coerce_json_if_needed(value)
	if not isinstance(coerced, list):
		raise ValueError(f"{fieldname} must be a list")
	return list(coerced)


def _coerce_json_if_needed(value: Any) -> Any:
	if isinstance(value, str):
		text = value.strip()
		if text.startswith("{") or text.startswith("["):
			try:
				return json.loads(text)
			except json.JSONDecodeError as exc:
				raise ValueError("JSON payload is invalid") from exc
	return value


def _coerce_bool(value: Any, fieldname: str) -> bool:
	if isinstance(value, bool):
		return value
	if isinstance(value, str):
		text = value.strip().lower()
		if text in {"true", "1", "yes"}:
			return True
		if text in {"false", "0", "no"}:
			return False
	raise ValueError(f"{fieldname} must be a bool")


def _coerce_int(value: Any, fieldname: str) -> int:
	if isinstance(value, bool):
		raise ValueError(f"{fieldname} must be an integer")
	try:
		if isinstance(value, str):
			text = value.strip()
			if not text or "." in text:
				raise ValueError
			return int(text)
		if isinstance(value, int):
			return value
	except ValueError as exc:
		raise ValueError(f"{fieldname} must be an integer") from exc
	raise ValueError(f"{fieldname} must be an integer")


def _load_sibling_module(filename: str, module_name: str):
	path = Path(__file__).with_name(filename)
	spec = importlib.util.spec_from_file_location(module_name, path)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


__all__ = [
	"preview_korea_kakao_template_registry_entry",
	"preview_korea_kakao_registered_queue_item",
	"preview_korea_kakao_provider_dispatch",
	"preview_korea_kakao_delivery_audit_event",
]
