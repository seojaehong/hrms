"""Framework-free unified approval inbox helpers."""

from __future__ import annotations

import datetime as dt
from typing import Any

OPEN_STATUSES = {"Open", "Pending", "Draft", "Submitted"}


def build_approval_inbox(
	records: list[dict[str, Any]],
	*,
	actor: str,
	today: dt.date | None = None,
	overdue_after_days: int = 3,
) -> list[dict[str, Any]]:
	"""Normalize mixed approval records into one actor-specific inbox."""

	if not actor:
		raise ValueError("actor is required")
	today = today or dt.date.today()
	items: list[dict[str, Any]] = []
	for record in records:
		if record.get("approver") != actor or record.get("status") not in OPEN_STATUSES:
			continue
		posting_date = _parse_date(record.get("posting_date"))
		age_days = (today - posting_date).days
		overdue = age_days > overdue_after_days
		items.append(
			{
				"source_doctype": record.get("doctype"),
				"name": record.get("name"),
				"employee": record.get("employee"),
				"approver": actor,
				"posting_date": posting_date.isoformat(),
				"status": record.get("status"),
				"age_days": age_days,
				"overdue": overdue,
				"priority": "High" if overdue else "Normal",
			}
		)
	return sorted(items, key=lambda item: (not item["overdue"], item["posting_date"], item["source_doctype"], item["name"]))


def summarize_inbox(items: list[dict[str, Any]]) -> dict[str, int]:
	"""Count inbox items by source DocType."""

	summary: dict[str, int] = {}
	for item in items:
		source = str(item.get("source_doctype") or "Unknown")
		summary[source] = summary.get(source, 0) + 1
	return summary


def _parse_date(value: Any) -> dt.date:
	if isinstance(value, dt.date):
		return value
	if isinstance(value, str):
		return dt.date.fromisoformat(value)
	raise TypeError("posting_date must be a date or ISO date string")


__all__ = ["OPEN_STATUSES", "build_approval_inbox", "summarize_inbox"]
