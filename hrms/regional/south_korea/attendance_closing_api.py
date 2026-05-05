"""Frappe-facing preview API for Korea attendance closing snapshots.

This module is preview-only: it shapes Attendance-like inputs into the
framework-free Korea attendance summary core without saving, submitting, or
mutating Frappe documents. Direct file tests run without a bench; inside Frappe
its function is whitelisted.
"""

from __future__ import annotations

import datetime as dt
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
def preview_korea_attendance_closing(
	*,
	workplace: str,
	period_start: Any,
	period_end: Any,
	records: Any,
	policy: Any,
	unmarked_days_by_employee: Any | None = None,
) -> dict[str, Any]:
	"""Return a side-effect-free Korea attendance closing preview snapshot."""

	attendance = _load_sibling_module("attendance_summary.py", "korea_attendance_summary")
	period_start_date = _coerce_date(period_start, "period_start")
	period_end_date = _coerce_date(period_end, "period_end")
	policy_mapping = _coerce_mapping(policy, "policy")
	unmarked = _coerce_optional_mapping(unmarked_days_by_employee, "unmarked_days_by_employee")
	normalized_records = [
		_build_attendance_record(attendance, row)
		for row in _coerce_list(records, "records")
	]

	closing_policy = attendance.ClosingPolicy(
		attendance_cutoff_day=policy_mapping.get("attendance_cutoff_day"),
		standard_work_hours_per_day=policy_mapping.get("standard_work_hours_per_day", 8.0),
		close_on_missing_attendance=policy_mapping.get("close_on_missing_attendance", False),
	)
	summary = attendance.summarize_attendance(
		normalized_records,
		period_start=period_start_date,
		period_end=period_end_date,
		unmarked_days_by_employee=unmarked,
	)
	blocking_messages = attendance.validate_summary_closable(summary, closing_policy)
	snapshot = attendance.build_closing_snapshot(
		workplace=workplace,
		period_start=period_start_date,
		period_end=period_end_date,
		summary_by_employee=summary,
		blocking_messages=blocking_messages,
	)

	return {
		"contract_type": "korea_attendance_closing_preview_v1",
		"runtime_action": "preview_only",
		"requires_runtime_apply": True,
		"snapshot": _json_safe(deepcopy(snapshot)),
	}


def _build_attendance_record(attendance, row: dict[str, Any]):
	row = deepcopy(row)
	if not row.get("attendance_date"):
		raise ValueError("attendance_date is required")
	return attendance.AttendanceRecord(
		employee=row.get("employee"),
		attendance_date=_coerce_date(row.get("attendance_date"), "attendance_date"),
		status=row.get("status"),
		half_day_status=row.get("half_day_status"),
		working_hours=row.get("working_hours"),
		late_entry=row.get("late_entry", False),
		early_exit=row.get("early_exit", False),
		overtime_hours=row.get("overtime_hours", 0.0),
		leave_type=row.get("leave_type"),
		holiday=row.get("holiday", False),
		weekly_off=row.get("weekly_off", False),
	)


def _coerce_list(value: Any, fieldname: str) -> list[dict[str, Any]]:
	coerced = _coerce_json_if_needed(value)
	if not isinstance(coerced, list):
		raise ValueError(f"{fieldname} must be a list or JSON array")
	if not all(isinstance(item, dict) for item in coerced):
		raise ValueError(f"{fieldname} entries must be dict objects")
	return deepcopy(coerced)


def _coerce_mapping(value: Any, fieldname: str) -> dict[str, Any]:
	coerced = _coerce_json_if_needed(value)
	if not isinstance(coerced, dict):
		raise ValueError(f"{fieldname} must be a dict or JSON object")
	return deepcopy(coerced)


def _coerce_optional_mapping(value: Any | None, fieldname: str) -> dict[str, Any] | None:
	if value is None:
		return None
	return _coerce_mapping(value, fieldname)


def _coerce_json_if_needed(value: Any) -> Any:
	if isinstance(value, str):
		text = value.strip()
		if text.startswith("{") or text.startswith("["):
			try:
				return json.loads(text)
			except json.JSONDecodeError as exc:
				raise ValueError("JSON payload is invalid") from exc
	return value


def _coerce_date(value: Any, fieldname: str) -> dt.date:
	if isinstance(value, dt.datetime):
		return value.date()
	if isinstance(value, dt.date):
		return value
	if isinstance(value, str):
		try:
			return dt.date.fromisoformat(value)
		except ValueError as exc:
			raise ValueError(f"{fieldname} must be an ISO date") from exc
	raise TypeError(f"{fieldname} must be a datetime.date or ISO date string")


def _json_safe(value: Any) -> Any:
	if isinstance(value, dt.date):
		return value.isoformat()
	if isinstance(value, dict):
		return {key: _json_safe(item) for key, item in value.items()}
	if isinstance(value, list):
		return [_json_safe(item) for item in value]
	return value


def _load_sibling_module(filename: str, module_name: str):
	path = Path(__file__).with_name(filename)
	spec = importlib.util.spec_from_file_location(module_name, path)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


__all__ = ["preview_korea_attendance_closing"]
