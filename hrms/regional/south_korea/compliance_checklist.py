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

CRITICAL_CHECK_CODES = {"payroll-close", "payslip-issue"}


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


def build_compliance_diagnosis(
	items: list[dict[str, Any]],
	*,
	evidence: dict[str, list[str]] | None = None,
	reviewer: str = "HR Compliance Review Queue",
) -> dict[str, Any]:
	"""Build a human-review compliance diagnosis contract.

	This intentionally returns deterministic findings and actions, not a legal
	opinion or numeric risk score. Evidence is caller-supplied so runtime adapters
	can attach documents later without this helper importing Frappe.
	"""

	if not isinstance(items, list):
		raise TypeError("items must be a list")
	reviewer = _require_text(reviewer, "reviewer")
	evidence = _normalize_evidence(evidence or {})
	item_rows = [_require_item_dict(item) for item in items]
	item_codes = {_require_text(item.get("code"), "item.code") for item in item_rows}
	unknown_codes = set(evidence) - item_codes
	if unknown_codes:
		raise ValueError(f"evidence contains unknown checklist codes: {sorted(unknown_codes)}")

	findings: list[dict[str, Any]] = []
	for item in item_rows:
		code = _require_text(item.get("code"), "item.code")
		status = _require_text(item.get("status", "Open"), "item.status")
		attached_evidence = list(evidence.get(code) or [])
		evidence_status = "attached" if attached_evidence else "missing"
		severity = _severity_for_item(code=code, status=status, evidence_status=evidence_status)
		findings.append(
			{
				"code": code,
				"label": _require_text(item.get("label"), "item.label"),
				"category": _require_text(item.get("category"), "item.category"),
				"status": status,
				"due_date": _require_text(item.get("due_date"), "item.due_date"),
				"owner": _require_text(item.get("owner"), "item.owner"),
				"severity": severity,
				"evidence_status": evidence_status,
				"evidence": attached_evidence,
				"action": _diagnosis_action(status=status, evidence_status=evidence_status),
			}
		)

	return {
		"contract_type": "korea_compliance_diagnosis_v1",
		"reviewer": reviewer,
		"summary": summarize_checklist(items),
		"requires_human_review": any(finding["severity"] in {"critical", "warning"} for finding in findings),
		"findings": findings,
	}


def _validate_period(period_start: dt.date, period_end: dt.date) -> None:
	if not isinstance(period_start, dt.date) or not isinstance(period_end, dt.date):
		raise TypeError("period_start and period_end must be datetime.date values")
	if period_start > period_end:
		raise ValueError("period_start cannot be after period_end")


def _severity_for_item(*, code: str, status: str, evidence_status: str) -> str:
	if status == "Overdue" and code in CRITICAL_CHECK_CODES:
		return "critical"
	if status == "Overdue":
		return "warning"
	if status == "Completed" and evidence_status == "missing":
		return "warning"
	return "ok"


def _diagnosis_action(*, status: str, evidence_status: str) -> dict[str, Any]:
	if status == "Overdue" and evidence_status == "missing":
		return {"action": "attach_evidence", "enabled": True, "requires_runtime_apply": True}
	if status == "Overdue":
		return {"action": "complete_overdue_check", "enabled": True, "requires_runtime_apply": True}
	if status == "Completed" and evidence_status == "missing":
		return {"action": "attach_evidence", "enabled": True, "requires_runtime_apply": True}
	return {"action": "review", "enabled": False, "requires_runtime_apply": False}


def _normalize_evidence(evidence: dict[str, list[str]]) -> dict[str, list[str]]:
	if not isinstance(evidence, dict):
		raise TypeError("evidence must be a dict")
	normalized: dict[str, list[str]] = {}
	for code, entries in evidence.items():
		code_text = _require_text(code, "evidence code")
		if not isinstance(entries, list):
			raise TypeError("evidence values must be lists")
		normalized[code_text] = [_require_text(entry, "evidence entry") for entry in entries]
	return normalized


def _require_item_dict(item: Any) -> dict[str, Any]:
	if not isinstance(item, dict):
		raise TypeError("items must contain dictionaries")
	return item


def _require_text(value: Any, fieldname: str) -> str:
	text = str(value or "").strip()
	if not text:
		raise ValueError(f"{fieldname} is required")
	return text


def _parse_date(value: str) -> dt.date:
	return dt.date.fromisoformat(value)


__all__ = [
	"build_compliance_checklist",
	"build_compliance_diagnosis",
	"evaluate_compliance_checklist",
	"summarize_checklist",
]
