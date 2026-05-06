"""Frappe-facing preview API for Korea payroll closing sessions.

This module wraps the framework-free payroll closing session read model in a
preview-only whitelisted API. It accepts JSON/dict payloads, delegates to the
pure helper by file-path import for no-bench execution, and never saves,
submits, approves, sends, or mutates runtime documents.
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
def preview_korea_payroll_closing_session(
	*,
	company: str,
	workplace: str,
	period_start: Any,
	period_end: Any,
	attendance_summary: Any,
	payroll_entry: Any,
	approval_state: Any,
	notification_state: Any,
	expense_state: Any | None = None,
) -> dict[str, Any]:
	"""Return a side-effect-free payroll closing session preview."""

	attendance_payload = deepcopy(_coerce_mapping(attendance_summary, "attendance_summary"))
	payroll_payload = deepcopy(_coerce_mapping(payroll_entry, "payroll_entry"))
	approval_payload = deepcopy(_coerce_mapping(approval_state, "approval_state"))
	notification_payload = deepcopy(_coerce_mapping(notification_state, "notification_state"))
	expense_payload = deepcopy(_coerce_mapping({} if expense_state is None else expense_state, "expense_state"))
	core = _load_sibling_module("payroll_closing_session.py", "korea_payroll_closing_session")

	session = core.build_korea_payroll_closing_session(
		company=company,
		workplace=workplace,
		period_start=period_start,
		period_end=period_end,
		attendance_summary=attendance_payload,
		payroll_entry=payroll_payload,
		approval_state=approval_payload,
		notification_state=notification_payload,
		expense_state=expense_payload,
	)
	session = deepcopy(session)
	session_contract_type = session.get("contract_type")
	session.update(
		{
			"contract_type": "korea_payroll_closing_session_preview_v1",
			"session_contract_type": session_contract_type,
			"runtime_action": "preview_only",
			"requires_runtime_apply": True,
		}
	)
	session["source"] = {
		"doctype": "Payroll Entry",
		"name": session.get("payroll_artifacts", {}).get("payroll_entry"),
	}
	return session


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


__all__ = ["preview_korea_payroll_closing_session"]
