"""Framework-free unified approval inbox helpers."""

from __future__ import annotations

import datetime as dt
from typing import Any

OPEN_STATUSES = {"Open", "Pending", "Draft", "Submitted"}
APPROVAL_ACTIONS = {"approve": "Approved", "reject": "Rejected"}


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
	overdue_after_days = _require_int(overdue_after_days, "overdue_after_days")
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


def build_approval_action(
	item: dict[str, Any],
	*,
	action: str,
	actor: str,
	note: str | None = None,
) -> dict[str, Any]:
	"""Build a side-effect-free approval/rejection action contract.

	The contract is intentionally not a Frappe mutation. Runtime adapters can use
	it later to call the correct DocType workflow methods with permission checks.
	"""

	_validate_action_item(item, action=action, actor=actor)
	return {
		"action_type": "korea_approval_action_v1",
		"action": action,
		"actor": actor,
		"target": {
			"doctype": str(item.get("source_doctype") or item.get("doctype") or "").strip(),
			"name": str(item.get("name") or "").strip(),
		},
		"result_status": APPROVAL_ACTIONS[action],
		"note": note,
		"requires_runtime_apply": True,
	}


def build_approval_batch_action(
	items: list[dict[str, Any]],
	*,
	action: str,
	actor: str,
	note: str | None = None,
) -> dict[str, Any]:
	"""Build an ordered batch approval action contract without side effects."""

	if not items:
		raise ValueError("at least one approval item is required")
	actions = [build_approval_action(item, action=action, actor=actor, note=note) for item in items]
	by_doctype: dict[str, int] = {}
	for entry in actions:
		doctype = entry["target"]["doctype"]
		by_doctype[doctype] = by_doctype.get(doctype, 0) + 1
	return {
		"batch_type": "korea_approval_batch_action_v1",
		"actor": actor,
		"action": action,
		"actions": actions,
		"summary": {"total": len(actions), "by_doctype": by_doctype},
		"requires_runtime_apply": True,
	}


def summarize_inbox(items: list[dict[str, Any]]) -> dict[str, int]:
	"""Count inbox items by source DocType."""

	summary: dict[str, int] = {}
	for item in items:
		source = str(item.get("source_doctype") or "Unknown")
		summary[source] = summary.get(source, 0) + 1
	return summary


def _validate_action_item(item: dict[str, Any], *, action: str, actor: str) -> None:
	if action not in APPROVAL_ACTIONS:
		raise ValueError(f"action must be one of {sorted(APPROVAL_ACTIONS)}")
	if not actor:
		raise ValueError("actor is required")
	if item.get("approver") != actor:
		raise ValueError("actor is not the assigned approver")
	if item.get("status") not in OPEN_STATUSES:
		raise ValueError("only open approval items can be actioned")
	if not str(item.get("source_doctype") or item.get("doctype") or "").strip():
		raise ValueError("source_doctype is required")
	if not str(item.get("name") or "").strip():
		raise ValueError("name is required")


def _parse_date(value: Any) -> dt.date:
	if isinstance(value, dt.date):
		return value
	if isinstance(value, str):
		return dt.date.fromisoformat(value)
	raise TypeError("posting_date must be a date or ISO date string")


def _require_int(value: Any, fieldname: str) -> int:
	if type(value) is not int:
		raise ValueError(f"{fieldname} must be an integer")
	return value


__all__ = [
	"OPEN_STATUSES",
	"APPROVAL_ACTIONS",
	"build_approval_inbox",
	"build_approval_action",
	"build_approval_batch_action",
	"summarize_inbox",
]
