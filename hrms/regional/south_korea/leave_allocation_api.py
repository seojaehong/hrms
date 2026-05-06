"""Frappe-facing preview API for Korea Leave Allocation drafts.

This module is intentionally preview-only: it turns Employee-shaped inputs into
reviewable Leave Allocation draft payloads without saving, submitting, or
mutating Frappe documents. Direct file tests run without a bench; inside Frappe
the function is whitelisted.
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
def preview_korea_leave_allocation_draft(
	*,
	employee: Any,
	as_of_date: Any,
	basis: str = "Hire Date",
	leave_type: str = "Annual Leave",
	fiscal_year_start_month: int = 1,
	fiscal_year_start_day: int = 1,
	existing_allocated_days: Any = 0,
) -> dict[str, Any]:
	"""Return a side-effect-free Korea Leave Allocation draft preview."""

	adapter = _load_sibling_module("leave_allocation_adapter.py", "korea_leave_allocation_adapter")
	draft = adapter.build_korea_leave_allocation_draft(
		employee=_coerce_mapping(employee, "employee"),
		as_of_date=as_of_date,
		basis=basis,
		leave_type=leave_type,
		fiscal_year_start_month=_coerce_int(fiscal_year_start_month, "fiscal_year_start_month"),
		fiscal_year_start_day=_coerce_int(fiscal_year_start_day, "fiscal_year_start_day"),
		existing_allocated_days=existing_allocated_days,
	)
	return {
		"contract_type": "korea_leave_allocation_preview_v1",
		"runtime_action": "preview_only",
		"requires_runtime_apply": True,
		"draft": deepcopy(draft),
	}


def _coerce_mapping(value: Any, fieldname: str) -> dict[str, Any]:
	coerced = _coerce_json_if_needed(value)
	if not isinstance(coerced, dict):
		raise ValueError(f"{fieldname} must be a dict or JSON object")
	return deepcopy(coerced)


def _coerce_json_if_needed(value: Any) -> Any:
	if isinstance(value, str):
		text = value.strip()
		if text.startswith("{") or text.startswith("["):
			try:
				return json.loads(text)
			except json.JSONDecodeError as exc:
				raise ValueError("JSON payload is invalid") from exc
	return value


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


__all__ = ["preview_korea_leave_allocation_draft"]
