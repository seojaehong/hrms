"""Framework-free South Korea compliance checklist MVP."""

from __future__ import annotations

import datetime as dt
from typing import Any

DEFAULT_CHECKS = (
	("payroll-close", "Payroll monthly close", "payroll", 10),
	("payslip-issue", "Issue employee payslips", "payroll", 10),
	("attendance-archive", "Archive attendance closing evidence", "attendance", 30),
	("labor-contract-review", "Review labor contract changes", "labor", 0),
)


def build_compliance_checklist(
	*,
	period_start: dt.date,
	period_end: dt.date,
	owners: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
	"""Build a deterministic recurring Korea HR compliance checklist."""

	_validate_period(period_start, period_end)
	owners = owners or {}
	items: list[dict[str, Any]] = []
	for code, label, category, due_offset in DEFAULT_CHECKS:
		due_date = period_end + dt.timedelta(days=due_offset)
		items.append(
			{
				"code": code,
				"label": label,
				"category": category,
				"period_start": period_start.isoformat(),
				"period_end": period_end.isoformat(),
				"due_date": due_date.isoformat(),
				"owner": owners.get(category, "HR Manager"),
				"status": "Open",
			}
		)
	return items


def evaluate_compliance_checklist(
	items: list[dict[str, Any]],
	*,
	completed_codes: set[str] | None = None,
	today: dt.date | None = None,
) -> list[dict[str, Any]]:
	"""Mark checklist items as Completed, Overdue, or Open."""

	completed_codes = completed_codes or set()
	today = today or dt.date.today()
	evaluated: list[dict[str, Any]] = []
	for item in items:
		updated = dict(item)
		if item.get("code") in completed_codes:
			updated["status"] = "Completed"
		elif _parse_date(str(item["due_date"])) < today:
			updated["status"] = "Overdue"
		else:
			updated["status"] = "Open"
		evaluated.append(updated)
	return evaluated


def summarize_checklist(items: list[dict[str, Any]]) -> dict[str, int]:
	"""Count checklist items by status."""

	summary = {"Completed": 0, "Open": 0, "Overdue": 0}
	for item in items:
		status = item.get("status", "Open")
		if status not in summary:
			summary[status] = 0
		summary[status] += 1
	return summary


def _validate_period(period_start: dt.date, period_end: dt.date) -> None:
	if not isinstance(period_start, dt.date) or not isinstance(period_end, dt.date):
		raise TypeError("period_start and period_end must be datetime.date values")
	if period_start > period_end:
		raise ValueError("period_start cannot be after period_end")


def _parse_date(value: str) -> dt.date:
	return dt.date.fromisoformat(value)


__all__ = ["build_compliance_checklist", "evaluate_compliance_checklist", "summarize_checklist"]
