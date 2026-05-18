"""Framework-free adapter from Employee-shaped data to Korea Leave Allocation drafts.

The helpers in this module avoid Frappe imports and database mutation. They turn
Korea annual leave reference calculations into a reviewable Leave Allocation-
shaped payload that a later runtime adapter can apply safely.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


def build_korea_leave_allocation_draft(
	*,
	employee: Any,
	as_of_date: dt.date | dt.datetime | str,
	basis: str = "Hire Date",
	leave_type: str = "Annual Leave",
	fiscal_year_start_month: int = 1,
	fiscal_year_start_day: int = 1,
	existing_allocated_days: int | float | str = 0,
) -> dict[str, Any]:
	"""Build a Leave Allocation-shaped draft from Employee-shaped data.

	The returned payload is intentionally side-effect-free. It includes the
	calculation reference and marks that runtime application is still required.
	"""

	annual_leave = _load_sibling_module("annual_leave.py", "korea_annual_leave")
	employee_id = _require_text(_get_value(employee, "name"), "employee.name")
	hire_date = _parse_date(_get_value(employee, "date_of_joining"), "employee.date_of_joining")
	effective_as_of = _parse_date(as_of_date, "as_of_date")
	employment_end_date = _optional_date(
		_get_value(employee, "relieving_date") or _get_value(employee, "employment_end_date"),
		"employee.relieving_date",
	)
	existing_days = _normalize_non_negative_number(existing_allocated_days, "existing_allocated_days")

	entitlement = annual_leave.calculate_annual_leave_entitlement(
		hire_date=hire_date,
		as_of_date=effective_as_of,
		basis=basis,
		fiscal_year_start_month=fiscal_year_start_month,
		fiscal_year_start_day=fiscal_year_start_day,
		employment_end_date=employment_end_date,
	)
	period_end = min(entitlement["period_end"], employment_end_date) if employment_end_date else entitlement["period_end"]
	new_leaves_allocated = max(0, round(entitlement["total_entitlement_days"] - existing_days, 2))

	return {
		"contract_type": "korea_leave_allocation_draft_v1",
		"source": {"doctype": "Employee", "name": employee_id},
		"doctype": "Leave Allocation",
		"employee": employee_id,
		"employee_name": _optional_text(_get_value(employee, "employee_name")),
		"company": _optional_text(_get_value(employee, "company")),
		"leave_type": _require_text(leave_type, "leave_type"),
		"from_date": entitlement["period_start"].isoformat(),
		"to_date": period_end.isoformat(),
		"new_leaves_allocated": new_leaves_allocated,
		"unused_leaves": new_leaves_allocated,
		"total_reference_entitlement": entitlement["total_entitlement_days"],
		"existing_allocated_days": existing_days,
		"carry_forward": False,
		"requires_runtime_apply": True,
		"entitlement_reference": _serialize_entitlement(entitlement),
	}


def _serialize_entitlement(entitlement: dict[str, Any]) -> dict[str, Any]:
	payload = dict(entitlement)
	for key in ("hire_date", "as_of_date", "employment_end_date", "period_start", "period_end"):
		if payload.get(key) is not None:
			payload[key] = payload[key].isoformat()
	return payload


def _parse_date(value: Any, fieldname: str) -> dt.date:
	if isinstance(value, dt.datetime):
		return value.date()
	if isinstance(value, dt.date):
		return value
	return _parse_iso_date(value, fieldname)


def _parse_iso_date(value: Any, fieldname: str) -> dt.date:
	text = _require_text(value, fieldname)
	try:
		return dt.date.fromisoformat(text)
	except ValueError as exc:
		raise ValueError(f"{fieldname} must be a valid ISO date") from exc


def _optional_date(value: Any, fieldname: str) -> dt.date | None:
	if value in (None, ""):
		return None
	return _parse_date(value, fieldname)


def _normalize_non_negative_number(value: Any, fieldname: str) -> int | float:
	if isinstance(value, bool):
		raise ValueError(f"{fieldname} must be finite")
	try:
		number = Decimal(str(value))
	except (InvalidOperation, ValueError) as exc:
		raise ValueError(f"{fieldname} must be finite") from exc
	if not number.is_finite():
		raise ValueError(f"{fieldname} must be finite")
	if number < 0:
		raise ValueError(f"{fieldname} cannot be negative")
	if number == number.to_integral_value():
		return int(number)
	return float(number)


def _get_value(source: Any, key: str, default: Any = None) -> Any:
	if isinstance(source, dict):
		return source.get(key, default)
	return getattr(source, key, default)


def _require_text(value: Any, fieldname: str) -> str:
	text = str(value or "").strip()
	if not text:
		raise ValueError(f"{fieldname} is required")
	return text


def _optional_text(value: Any) -> str | None:
	text = str(value or "").strip()
	return text or None


def _load_sibling_module(filename: str, module_name: str):
	path = Path(__file__).with_name(filename)
	spec = importlib.util.spec_from_file_location(module_name, path)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


__all__ = ["build_korea_leave_allocation_draft"]
