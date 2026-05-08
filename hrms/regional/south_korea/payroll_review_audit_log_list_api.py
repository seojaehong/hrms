"""Frappe-facing preview API for Korea payroll review audit-log lists.

This wrapper exposes the framework-free payroll review audit-log operator list as
a preview-only API contract. It accepts JSON/list inputs, delegates by file-path
import for no-bench execution, and never saves, submits, approves, sends,
creates payroll documents, or mutates runtime state.
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
def preview_korea_payroll_review_audit_log_list(
	*,
	company: str,
	rows: Any,
	workplaces: Any | None = None,
) -> dict[str, Any]:
	"""Return a scoped, route-only payroll review audit-log list preview."""

	row_payloads = deepcopy(_coerce_list(rows, "rows"))
	workplace_payloads = None if workplaces is None else deepcopy(_coerce_list(workplaces, "workplaces"))
	core = _load_sibling_module("payroll_review_audit_log_list.py", "korea_payroll_review_audit_log_list")

	audit_log_list = core.build_korea_payroll_review_audit_log_list(
		row_payloads,
		company=company,
		workplaces=workplace_payloads,
	)
	audit_log_list = deepcopy(audit_log_list)
	audit_log_list_contract_type = audit_log_list.get("contract_type")
	audit_log_list.update(
		{
			"contract_type": "korea_payroll_review_audit_log_list_preview_v1",
			"audit_log_list_contract_type": audit_log_list_contract_type,
			"runtime_action": "preview_only",
			"requires_runtime_apply": False,
		}
	)
	return audit_log_list


def _coerce_list(value: Any, fieldname: str) -> list[Any]:
	coerced = _coerce_json_if_needed(value)
	if not isinstance(coerced, list):
		raise ValueError(f"{fieldname} must be a list or JSON array")
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


__all__ = ["preview_korea_payroll_review_audit_log_list"]
