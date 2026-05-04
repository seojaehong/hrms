"""Framework-free Korea closing center contract helpers.

The closing center is an orchestration contract for admin home / monthly close UX.
It intentionally has no Frappe imports: adapters can shape Attendance Closing,
Payroll Verification, approvals, and compliance records into the item dictionaries
accepted here, while this module keeps filtering, blocker, action, and drilldown
semantics directly testable without a bench runtime.
"""

from __future__ import annotations

import datetime as dt
import math
from typing import Any

SUPPORTED_CLOSING_STATUSES = {"Draft", "Pending", "Ready", "Ready To Close", "Blocked", "Closed"}
READY_STATUSES = {"Ready", "Ready To Close"}
CLOSED_STATUSES = {"Closed"}


def build_closing_center(*, workplace: str, period: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]:
	"""Build a deterministic workplace-scoped Korea monthly closing center payload."""

	workplace = _require_text(workplace, "workplace")
	period_payload = _normalize_period(period)
	cards: list[dict[str, Any]] = []
	blockers: list[dict[str, str]] = []
	actions: list[dict[str, Any]] = []
	drilldowns: dict[str, list[str]] = {}

	for item in items:
		if not isinstance(item, dict):
			raise TypeError("items must contain dictionaries")
		if _require_text(item.get("workplace"), "item.workplace") != workplace:
			continue

		card = _normalize_card(item)
		cards.append(card)
		drilldowns.setdefault(card["source_doctype"], []).append(card["name"])

		for message in card["blockers"]:
			blockers.append({"source_doctype": card["source_doctype"], "name": card["name"], "message": message})
		actions.append(_build_action(card))

	summary = _summarize_cards(cards)
	status = _center_status(summary)

	return {
		"workplace": workplace,
		"period": period_payload,
		"status": status,
		"summary": summary,
		"cards": cards,
		"blockers": blockers,
		"actions": actions,
		"drilldowns": {doctype: drilldowns[doctype] for doctype in sorted(drilldowns)},
	}


def _normalize_period(period: dict[str, Any]) -> dict[str, str]:
	if not isinstance(period, dict):
		raise TypeError("period must be a dictionary")
	start_date = _parse_iso_date(period.get("start_date"), "period.start_date")
	end_date = _parse_iso_date(period.get("end_date"), "period.end_date")
	if start_date > end_date:
		raise ValueError("period.start_date cannot be after period.end_date")
	return {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()}


def _normalize_card(item: dict[str, Any]) -> dict[str, Any]:
	source_doctype = _require_text(item.get("doctype") or item.get("source_doctype"), "item.doctype")
	name = _require_text(item.get("name"), "item.name")
	status = _require_text(item.get("status"), "item.status")
	if status not in SUPPORTED_CLOSING_STATUSES:
		raise ValueError(f"unsupported closing status: {status}")

	metrics = _normalize_metrics(item.get("metrics") or {})
	blockers = _normalize_blockers(item.get("blockers") or [])
	if blockers and status != "Blocked":
		status = "Blocked"

	return {
		"source_doctype": source_doctype,
		"name": name,
		"status": status,
		"severity": _severity_for(status),
		"metrics": metrics,
		"blockers": blockers,
		"drilldown": {"source_doctype": source_doctype, "name": name},
	}


def _normalize_metrics(metrics: dict[str, Any]) -> dict[str, int | float | str]:
	if not isinstance(metrics, dict):
		raise TypeError("metrics must be a dictionary")
	normalized: dict[str, int | float | str] = {}
	for key, value in sorted(metrics.items()):
		fieldname = f"metrics.{key}"
		if isinstance(value, bool):
			raise ValueError(f"{fieldname} must be a number or text")
		if isinstance(value, (int, float)):
			if not math.isfinite(float(value)):
				raise ValueError(f"{fieldname} must be finite")
			if float(value) < 0:
				raise ValueError(f"{fieldname} cannot be negative")
			normalized[str(key)] = value
		else:
			normalized[str(key)] = _require_text(value, fieldname)
	return normalized


def _normalize_blockers(blockers: Any) -> list[str]:
	if not isinstance(blockers, list):
		raise TypeError("blockers must be a list")
	return [_require_text(message, "blocker") for message in blockers]


def _build_action(card: dict[str, Any]) -> dict[str, Any]:
	base = {"source_doctype": card["source_doctype"], "name": card["name"]}
	if card["status"] == "Blocked":
		return {**base, "action": "resolve_blockers", "label": "Resolve blockers", "enabled": False, "reason": "blocking items must be cleared first"}
	if card["status"] in CLOSED_STATUSES:
		return {**base, "action": "view_audit_log", "label": "View audit log", "enabled": True}
	if card["status"] in READY_STATUSES:
		return {**base, "action": "submit_for_approval", "label": "Submit for approval", "enabled": True}
	return {**base, "action": "continue_preparation", "label": "Continue preparation", "enabled": True}


def _summarize_cards(cards: list[dict[str, Any]]) -> dict[str, int]:
	blocked_items = sum(1 for card in cards if card["status"] == "Blocked")
	ready_items = sum(1 for card in cards if card["status"] in READY_STATUSES)
	closed_items = sum(1 for card in cards if card["status"] in CLOSED_STATUSES)
	return {
		"total_items": len(cards),
		"blocked_items": blocked_items,
		"ready_items": ready_items,
		"closed_items": closed_items,
	}


def _center_status(summary: dict[str, int]) -> str:
	if summary["blocked_items"]:
		return "Blocked"
	if summary["total_items"] and summary["ready_items"] + summary["closed_items"] == summary["total_items"]:
		return "Ready To Close"
	return "Preparing"


def _severity_for(status: str) -> str:
	if status == "Blocked":
		return "danger"
	if status in READY_STATUSES:
		return "warning"
	if status in CLOSED_STATUSES:
		return "success"
	return "neutral"


def _require_text(value: Any, fieldname: str) -> str:
	text = str(value or "").strip()
	if not text:
		raise ValueError(f"{fieldname} is required")
	return text


def _parse_iso_date(value: Any, fieldname: str) -> dt.date:
	text = _require_text(value, fieldname)
	try:
		return dt.date.fromisoformat(text)
	except ValueError as exc:
		raise ValueError(f"{fieldname} must be a valid ISO date") from exc


__all__ = ["SUPPORTED_CLOSING_STATUSES", "build_closing_center"]
