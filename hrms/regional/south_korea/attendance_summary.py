"""South Korea attendance summary and monthly closing helpers.

This module is intentionally framework-free. Frappe adapters can shape
Attendance/Holiday/Profile documents into these data structures later, while the
core closing math remains directly testable without a bench runtime.
"""

from __future__ import annotations

import calendar
import datetime as dt
import hashlib
import json
import math
from typing import Any


SUPPORTED_ATTENDANCE_STATUSES = {
	"Present",
	"Absent",
	"On Leave",
	"Half Day",
	"Work From Home",
}


class AttendanceRecord:
	"""Normalized attendance input for one employee/date."""

	__slots__ = (
		"employee",
		"attendance_date",
		"status",
		"half_day_status",
		"working_hours",
		"late_entry",
		"early_exit",
		"overtime_hours",
		"leave_type",
		"holiday",
		"weekly_off",
	)

	def __init__(
		self,
		*,
		employee: str,
		attendance_date: dt.date,
		status: str,
		half_day_status: str | None = None,
		working_hours: float | None = None,
		late_entry: bool = False,
		early_exit: bool = False,
		overtime_hours: float = 0.0,
		leave_type: str | None = None,
		holiday: bool = False,
		weekly_off: bool = False,
	) -> None:
		if not employee:
			raise ValueError("employee is required")
		if not isinstance(attendance_date, dt.date):
			raise TypeError("attendance_date must be a datetime.date")
		if status not in SUPPORTED_ATTENDANCE_STATUSES:
			raise ValueError(f"unsupported attendance status: {status}")
		if half_day_status not in {None, "Present", "Absent"}:
			raise ValueError("half_day_status must be Present, Absent, or None")
		if working_hours is not None:
			_validate_non_negative_finite("working_hours", working_hours)
		_validate_non_negative_finite("overtime_hours", overtime_hours)

		self.employee = employee
		self.attendance_date = attendance_date
		self.status = status
		self.half_day_status = half_day_status
		self.working_hours = float(working_hours or 0.0)
		self.late_entry = bool(late_entry)
		self.early_exit = bool(early_exit)
		self.overtime_hours = float(overtime_hours or 0.0)
		self.leave_type = leave_type
		self.holiday = bool(holiday)
		self.weekly_off = bool(weekly_off)


class ClosingPolicy:
	"""Policy flags used by closing validation."""

	__slots__ = (
		"attendance_cutoff_day",
		"standard_work_hours_per_day",
		"close_on_missing_attendance",
	)

	def __init__(
		self,
		*,
		attendance_cutoff_day: int,
		standard_work_hours_per_day: float = 8.0,
		close_on_missing_attendance: bool = False,
	) -> None:
		_validate_cutoff_day(attendance_cutoff_day)
		if standard_work_hours_per_day <= 0:
			raise ValueError("standard_work_hours_per_day must be positive")

		self.attendance_cutoff_day = attendance_cutoff_day
		self.standard_work_hours_per_day = float(standard_work_hours_per_day)
		self.close_on_missing_attendance = bool(close_on_missing_attendance)


def closing_period_for(as_of_date: dt.date, cutoff_day: int) -> tuple[dt.date, dt.date]:
	"""Return the attendance closing period containing or following as_of_date.

	Examples:
	- cutoff_day=25, as_of=2026-05-20 -> 2026-04-26 through 2026-05-25
	- cutoff_day=25, as_of=2026-05-26 -> 2026-05-26 through 2026-06-25
	- cutoff_day=31 clamps to each month's last day.
	"""

	if not isinstance(as_of_date, dt.date):
		raise TypeError("as_of_date must be a datetime.date")
	_validate_cutoff_day(cutoff_day)

	current_cutoff = _clamped_date(as_of_date.year, as_of_date.month, cutoff_day)
	if as_of_date <= current_cutoff:
		period_end = current_cutoff
		previous_month = _add_months(period_end.replace(day=1), -1)
		previous_cutoff = _clamped_date(previous_month.year, previous_month.month, cutoff_day)
		period_start = previous_cutoff + dt.timedelta(days=1)
	else:
		period_start = current_cutoff + dt.timedelta(days=1)
		next_month = _add_months(current_cutoff.replace(day=1), 1)
		period_end = _clamped_date(next_month.year, next_month.month, cutoff_day)

	return period_start, period_end


def summarize_attendance(
	records: list[AttendanceRecord],
	*,
	period_start: dt.date,
	period_end: dt.date,
	unmarked_days_by_employee: dict[str, float] | None = None,
) -> dict[str, dict[str, Any]]:
	"""Summarize normalized attendance records by employee.

	The function intentionally does not infer employment calendars or holidays.
	Adapters should provide shaped records and any unmarked dates explicitly in a
	future integration layer.
	"""

	if period_start > period_end:
		raise ValueError("period_start cannot be after period_end")

	summary_by_employee: dict[str, dict[str, Any]] = {}
	seen: set[tuple[str, dt.date]] = set()

	for record in records:
		if not isinstance(record, AttendanceRecord):
			raise TypeError("records must contain AttendanceRecord instances")
		if record.attendance_date < period_start or record.attendance_date > period_end:
			continue

		key = (record.employee, record.attendance_date)
		if key in seen:
			raise ValueError(
				f"duplicate attendance record for {record.employee} on {record.attendance_date}"
			)
		seen.add(key)

		employee_summary = summary_by_employee.setdefault(record.employee, _empty_summary())
		_apply_record(employee_summary, record)

	for employee, unmarked_days in sorted((unmarked_days_by_employee or {}).items()):
		if not employee:
			raise ValueError("unmarked employee key is required")
		_validate_non_negative_finite("unmarked_days", unmarked_days)
		employee_summary = summary_by_employee.setdefault(employee, _empty_summary())
		employee_summary["unmarked_days"] = round(float(unmarked_days), 4)

	return {employee: _finalize_summary(values) for employee, values in sorted(summary_by_employee.items())}


def validate_summary_closable(
	summary_by_employee: dict[str, dict[str, Any]],
	policy: ClosingPolicy,
) -> list[str]:
	"""Return blocking messages for a Korea monthly attendance closing."""

	messages: list[str] = []
	for employee, summary in sorted(summary_by_employee.items()):
		if summary.get("unresolved_half_days", 0):
			messages.append(
				f"{employee}: unresolved half-day attendance must be classified before closing"
			)
		if policy.close_on_missing_attendance and summary.get("unmarked_days", 0):
			messages.append(f"{employee}: unmarked attendance remains before closing")

	return messages


def build_closing_snapshot(
	*,
	workplace: str,
	period_start: dt.date,
	period_end: dt.date,
	summary_by_employee: dict[str, dict[str, Any]],
	blocking_messages: list[str] | None = None,
) -> dict[str, Any]:
	"""Build a deterministic side-effect-free monthly closing snapshot payload."""

	if not workplace:
		raise ValueError("workplace is required")
	if period_start > period_end:
		raise ValueError("period_start cannot be after period_end")

	blocking_messages = list(blocking_messages or [])
	normalized_summary = {
		employee: _normalize_for_json(summary_by_employee[employee])
		for employee in sorted(summary_by_employee)
	}
	canonical_payload = {
		"workplace": workplace,
		"period_start": period_start.isoformat(),
		"period_end": period_end.isoformat(),
		"summary_by_employee": normalized_summary,
	}
	summary_hash = hashlib.sha256(
		json.dumps(canonical_payload, sort_keys=True, separators=(",", ":")).encode()
	).hexdigest()

	return {
		"workplace": workplace,
		"period_start": period_start,
		"period_end": period_end,
		"employees": sorted(summary_by_employee),
		"summary_by_employee": normalized_summary,
		"summary_hash": summary_hash,
		"blocking_messages": blocking_messages,
		"status": "Blocked" if blocking_messages else "Ready To Close",
	}


def _apply_record(summary: dict[str, Any], record: AttendanceRecord) -> None:
	summary["records_count"] += 1
	summary["working_hours"] += record.working_hours
	summary["overtime_hours"] += record.overtime_hours

	if record.late_entry:
		summary["late_entries"] += 1
	if record.early_exit:
		summary["early_exits"] += 1
	if record.holiday:
		summary["holiday_days"] += 1
	if record.weekly_off:
		summary["weekly_off_days"] += 1

	if record.status in {"Present", "Work From Home"}:
		summary["present_days"] += 1.0
		if record.holiday:
			summary["worked_on_holiday_days"] += 1
		if record.weekly_off:
			summary["worked_on_weekly_off_days"] += 1
	elif record.status == "Absent":
		summary["absent_days"] += 1.0
	elif record.status == "On Leave":
		summary["leave_days"] += 1.0
	elif record.status == "Half Day":
		_apply_half_day(summary, record)


def _apply_half_day(summary: dict[str, Any], record: AttendanceRecord) -> None:
	if record.half_day_status == "Absent":
		summary["present_days"] += 0.5
		summary["absent_days"] += 0.5
	elif record.half_day_status == "Present":
		summary["present_days"] += 1.0
	else:
		summary["present_days"] += 0.5
		summary["unresolved_half_days"] += 1

	if record.holiday:
		summary["worked_on_holiday_days"] += 1
	if record.weekly_off:
		summary["worked_on_weekly_off_days"] += 1


def _empty_summary() -> dict[str, Any]:
	return {
		"present_days": 0.0,
		"absent_days": 0.0,
		"leave_days": 0.0,
		"holiday_days": 0,
		"weekly_off_days": 0,
		"worked_on_holiday_days": 0,
		"worked_on_weekly_off_days": 0,
		"unmarked_days": 0.0,
		"unresolved_half_days": 0,
		"late_entries": 0,
		"early_exits": 0,
		"working_hours": 0.0,
		"overtime_hours": 0.0,
		"records_count": 0,
	}


def _finalize_summary(summary: dict[str, Any]) -> dict[str, Any]:
	return {key: _round_if_float(value) for key, value in summary.items()}


def _round_if_float(value: Any) -> Any:
	if isinstance(value, float):
		return round(value, 4)
	return value


def _normalize_for_json(value: Any) -> Any:
	if isinstance(value, dict):
		return {key: _normalize_for_json(value[key]) for key in sorted(value)}
	if isinstance(value, (list, tuple)):
		return [_normalize_for_json(item) for item in value]
	if isinstance(value, dt.date):
		return value.isoformat()
	return _round_if_float(value)


def _validate_non_negative_finite(fieldname: str, value: float) -> None:
	try:
		number = float(value)
	except (TypeError, ValueError) as exc:
		raise ValueError(f"{fieldname} must be a number") from exc
	if not math.isfinite(number):
		raise ValueError(f"{fieldname} must be finite")
	if number < 0:
		raise ValueError(f"{fieldname} cannot be negative")


def _validate_cutoff_day(cutoff_day: int) -> None:
	if not isinstance(cutoff_day, int):
		raise TypeError("cutoff_day must be an integer")
	if cutoff_day < 1 or cutoff_day > 31:
		raise ValueError("cutoff_day must be between 1 and 31")


def _clamped_date(year: int, month: int, day: int) -> dt.date:
	last_day = calendar.monthrange(year, month)[1]
	return dt.date(year, month, min(day, last_day))


def _add_months(date_value: dt.date, months: int) -> dt.date:
	month_index = date_value.month - 1 + months
	year = date_value.year + month_index // 12
	month = month_index % 12 + 1
	return dt.date(year, month, 1)
