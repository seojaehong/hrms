"""Framework-free Korea mobile ESS/MSS API contract helpers.

These helpers shape employee self-service and manager self-service payloads for
mobile/API adapters without importing Frappe or mutating workflow state.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal, InvalidOperation
from typing import Any

OPEN_STATUSES = {"Open", "Pending", "Draft", "Submitted"}


def build_mobile_employee_home(*, employee: str, period: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
	"""Build an employee-scoped mobile ESS home contract."""

	employee = _require_text(employee, "employee")
	period_payload = _normalize_period(period)
	if not isinstance(records, list):
		raise TypeError("records must be a list")

	attendance_status: dict[str, str] | None = None
	leave_balances: list[dict[str, int | float | str]] = []
	payslips: list[dict[str, str]] = []

	for record in records:
		_record = _require_record_dict(record)
		if _record.get("employee") != employee:
			continue
		record_type = _require_text(_record.get("record_type"), "record.record_type")
		if record_type == "attendance":
			attendance_status = {
				"status": _require_text(_record.get("status"), "attendance.status"),
				"workplace": _require_text(_record.get("workplace"), "attendance.workplace"),
			}
		elif record_type == "leave_balance":
			leave_balances.append(
				{
					"leave_type": _require_text(_record.get("leave_type"), "leave_balance.leave_type"),
					"remaining_days": _normalize_non_negative_number(_record.get("remaining_days"), "remaining_days"),
				}
			)
		elif record_type == "payslip":
			payslips.append(
				{
					"name": _require_text(_record.get("name"), "payslip.name"),
					"status": _require_text(_record.get("status"), "payslip.status"),
				}
			)

	return {
		"contract_type": "korea_mobile_ess_home_v1",
		"employee": employee,
		"period": period_payload,
		"attendance_status": attendance_status,
		"leave_balances": sorted(leave_balances, key=lambda row: str(row["leave_type"])),
		"payslips": sorted(payslips, key=lambda row: str(row["name"])),
		"quick_actions": _employee_quick_actions(has_payslips=bool(payslips)),
	}


def build_mobile_manager_worklist(
	*,
	manager: str,
	period: dict[str, Any],
	workplace: str | None = None,
	records: list[dict[str, Any]],
	today: dt.date | None = None,
	overdue_after_days: int = 3,
) -> dict[str, Any]:
	"""Build a manager-scoped mobile MSS worklist contract."""

	manager = _require_text(manager, "manager")
	workplace = _require_text(workplace, "workplace") if workplace is not None else None
	period_payload = _normalize_period(period)
	period_start = dt.date.fromisoformat(period_payload["start_date"])
	period_end = dt.date.fromisoformat(period_payload["end_date"])
	if not isinstance(records, list):
		raise TypeError("records must be a list")
	overdue_after_days = _require_int(overdue_after_days, "overdue_after_days")
	if overdue_after_days < 0:
		raise ValueError("overdue_after_days cannot be negative")
	if today is None:
		raise ValueError("today is required")

	items: list[dict[str, Any]] = []
	for record in records:
		_record = _require_record_dict(record)
		if _record.get("manager") != manager:
			continue
		if workplace is not None and _record.get("workplace") != workplace:
			continue
		if _record.get("status") not in OPEN_STATUSES:
			continue

		posting_date = _parse_iso_date(_record.get("posting_date"), "record.posting_date")
		if posting_date > today:
			raise ValueError("record.posting_date cannot be after today")
		if not period_start <= posting_date <= period_end:
			continue
		age_days = (today - posting_date).days
		overdue = age_days > overdue_after_days
		items.append(
			{
				"source_doctype": _require_text(_record.get("doctype") or _record.get("source_doctype"), "record.doctype"),
				"name": _require_text(_record.get("name"), "record.name"),
				"employee": _require_text(_record.get("employee"), "record.employee"),
				"status": _require_text(_record.get("status"), "record.status"),
				"posting_date": posting_date.isoformat(),
				"age_days": age_days,
				"overdue": overdue,
				"priority": "High" if overdue else "Normal",
				"action": {"action": "review_approval", "enabled": True, "requires_runtime_apply": True},
			}
		)

	items = sorted(items, key=lambda item: (not item["overdue"], item["posting_date"], item["source_doctype"], item["name"]))
	return {
		"contract_type": "korea_mobile_mss_worklist_v1",
		"manager": manager,
		"workplace": workplace,
		"period": period_payload,
		"summary": _summarize_worklist(items),
		"items": items,
	}


def _employee_quick_actions(*, has_payslips: bool) -> list[dict[str, Any]]:
	actions = [{"action": "request_leave", "enabled": True, "requires_runtime_apply": True}]
	if has_payslips:
		actions.append({"action": "view_payslip", "enabled": True, "requires_runtime_apply": True})
	return actions


def _summarize_worklist(items: list[dict[str, Any]]) -> dict[str, Any]:
	by_doctype: dict[str, int] = {}
	for item in items:
		doctype = item["source_doctype"]
		by_doctype[doctype] = by_doctype.get(doctype, 0) + 1
	return {
		"total": len(items),
		"overdue": sum(1 for item in items if item["overdue"]),
		"by_doctype": by_doctype,
	}


def _normalize_period(period: dict[str, Any]) -> dict[str, str]:
	if not isinstance(period, dict):
		raise TypeError("period must be a dict")
	start_date = _parse_iso_date(period.get("start_date"), "period.start_date")
	end_date = _parse_iso_date(period.get("end_date"), "period.end_date")
	if start_date > end_date:
		raise ValueError("period.start_date cannot be after period.end_date")
	return {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()}


def _parse_iso_date(value: Any, fieldname: str) -> dt.date:
	text = _require_text(value, fieldname)
	try:
		return dt.date.fromisoformat(text)
	except ValueError as exc:
		raise ValueError(f"{fieldname} must be a valid ISO date") from exc


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


def _require_int(value: Any, fieldname: str) -> int:
	if isinstance(value, bool) or not isinstance(value, int):
		raise ValueError(f"{fieldname} must be an integer")
	return value


def _require_record_dict(record: Any) -> dict[str, Any]:
	if not isinstance(record, dict):
		raise TypeError("records must contain dictionaries")
	return record


def _require_text(value: Any, fieldname: str) -> str:
	text = str(value or "").strip()
	if not text:
		raise ValueError(f"{fieldname} is required")
	return text


__all__ = ["OPEN_STATUSES", "build_mobile_employee_home", "build_mobile_manager_worklist"]
