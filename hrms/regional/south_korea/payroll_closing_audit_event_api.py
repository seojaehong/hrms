"""Frappe-facing preview API for Korea payroll closing audit events.

This module wraps the framework-free payroll closing audit event contract in a
preview-only whitelisted API. It accepts JSON/dict session payloads, delegates to
the pure helper by file-path import for no-bench execution, and never saves,
submits, approves, sends, calls providers, or mutates runtime documents.
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
def preview_korea_payroll_closing_audit_event(
	*,
	session: Any,
	actor: Any,
	action: Any,
	note: Any = None,
) -> dict[str, Any]:
	"""Return a side-effect-free preview of a payroll closing audit event."""

	session_payload = deepcopy(_coerce_mapping(session, "session"))
	core = _load_sibling_module("payroll_closing_session.py", "korea_payroll_closing_session")
	event = deepcopy(
		core.build_korea_payroll_closing_audit_event(
			session_payload,
			actor=actor,
			action=action,
			note=note,
		)
	)
	audit_event_contract_type = event.get("contract_type")
	session_contract_type = event.get("session_contract_type")
	event.update(
		{
			"contract_type": "korea_payroll_closing_audit_event_preview_v1",
			"audit_event_contract_type": audit_event_contract_type,
			"source_session_contract_type": session_contract_type,
			"runtime_action": "preview_only",
			"requires_runtime_apply": True,
		}
	)
	return event


def _coerce_mapping(value: Any, fieldname: str) -> dict[str, Any]:
	coerced = _coerce_json_if_needed(value)
	if not isinstance(coerced, dict):
		raise ValueError(f"{fieldname} must be a dict or JSON object")
	return coerced


def _coerce_json_if_needed(value: Any) -> Any:
	if isinstance(value, str):
		text = value.strip()
		if text.startswith("{") or text.startswith("["):
			try:
				return json.loads(text)
			except json.JSONDecodeError as exc:
				raise ValueError("JSON payload is invalid") from exc
	return value


def _load_sibling_module(filename: str, module_name: str):
	path = Path(__file__).with_name(filename)
	spec = importlib.util.spec_from_file_location(module_name, path)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


__all__ = ["preview_korea_payroll_closing_audit_event"]
