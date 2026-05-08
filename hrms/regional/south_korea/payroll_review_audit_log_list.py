"""Framework-free Korea payroll review audit-log operator list contract.

This read model turns persisted review audit-log insert results into a scoped,
route-only operator list. It performs no Frappe lookup, save, submit, approval,
notification send, provider call, or payroll document creation.
"""

from __future__ import annotations

import datetime as dt
import re
from copy import deepcopy
from typing import Any
from urllib.parse import quote

CONTRACT_TYPE = "korea_payroll_review_audit_log_list_v1"
SOURCE_CONTRACT_TYPE = "korea_payroll_closing_review_audit_log_runtime_insert_v1"
SOURCE_API_CONTRACT_TYPE = "korea_payroll_closing_review_audit_log_runtime_insert_api_v1"
EXPECTED_RUNTIME_ACTION = "runtime_review_audit_log_created"
EXPECTED_MUTATION_BOUNDARY = "audit_log_only_no_submit_no_send_no_provider_call"
EXPECTED_DOCTYPE = "Korea Payroll Closing Review Audit Log"
EXPECTED_AI_ROLE = "assistant_only"
EXPECTED_PREVIOUS_STATUS = "draft_pending_human_approval"
EXPECTED_AUDIT_LOG_CONTRACT_TYPE = "korea_payroll_closing_draft_review_audit_log_v1"

_ALLOWED_ACTION_STATUSES = {
	"approve_draft": "draft_human_approved",
	"reject_draft": "draft_human_rejected",
	"request_changes": "draft_changes_requested",
}
_FORBIDDEN_SCORE_FRAGMENTS = (
	"score",
	"riskscore",
	"legalriskscore",
	"probability",
	"probabilityscore",
	"successrate",
	"closingsuccessrate",
)


def build_korea_payroll_review_audit_log_list(
	rows: list[dict[str, Any]],
	*,
	company: str,
	workplaces: list[str] | None = None,
	strict_scope: bool = False,
) -> dict[str, Any]:
	"""Build a scoped route-only audit-log list for payroll operators."""

	if not isinstance(rows, list):
		raise ValueError("rows must be a list")
	company_text = _require_text(company, "company")
	workplace_scope = _normalize_workplaces(workplaces)
	items: list[dict[str, Any]] = []

	for row in rows:
		if not isinstance(row, dict):
			raise ValueError("each audit row must be a JSON object")
		_reject_forbidden_score_keys(row)
		validated = _validate_row(row)
		if validated["company"] != company_text:
			if strict_scope:
				raise ValueError("audit row company must match requested company")
			continue
		if workplace_scope is not None and validated["workplace"] not in workplace_scope:
			if strict_scope:
				raise ValueError("audit row workplace is outside requested workplaces")
			continue
		items.append(_build_item(validated, row))

	items.sort(key=lambda item: (item["sort_created_at"], item["name"]), reverse=True)
	for item in items:
		item.pop("sort_created_at", None)
	return {
		"contract_type": CONTRACT_TYPE,
		"source_contract_type": SOURCE_CONTRACT_TYPE,
		"runtime_action": "preview_only",
		"requires_runtime_apply": False,
		"company": company_text,
		"workplaces": list(workplace_scope) if workplace_scope is not None else [],
		"total_count": len(items),
		"items": deepcopy(items),
		"action": {
			"action": "open_payroll_review_audit_logs",
			"route": "korea-payroll-review-audit-logs",
			"enabled": bool(items),
			"requires_runtime_apply": False,
		},
		"requires_human_approval": True,
		"ai_role": EXPECTED_AI_ROLE,
	}


def _build_item(validated: dict[str, Any], source_row: dict[str, Any]) -> dict[str, Any]:
	name = validated["name"]
	return {
		"source_contract_type": validated["contract_type"],
		"name": name,
		"draft_name": validated["draft_name"],
		"status": validated["status"],
		"action_taken": validated["action"],
		"previous_status": validated["previous_status"],
		"review_actor": validated["review_actor"],
		"audit_actor": validated["audit_actor"],
		"company": validated["company"],
		"workplace": validated["workplace"],
		"period_start": validated["period_start"],
		"period_end": validated["period_end"],
		"source_payroll_entry": validated["source_payroll_entry"],
		"created_at": validated["created_at"],
		"sort_created_at": validated["sort_created_at"],
		"route": f"korea-payroll-review-audit-logs/{quote(name, safe='')}",
		"action": {
			"action": "open_payroll_review_audit_log",
			"route": f"korea-payroll-review-audit-logs/{quote(name, safe='')}",
			"enabled": True,
			"requires_runtime_apply": False,
		},
		"source_audit_log": deepcopy(source_row),
		"requires_human_approval": True,
		"ai_role": EXPECTED_AI_ROLE,
	}


def _validate_row(row: dict[str, Any]) -> dict[str, Any]:
	contract_type = row.get("contract_type")
	if contract_type == SOURCE_API_CONTRACT_TYPE:
		if row.get("runtime_insert_contract_type") != SOURCE_CONTRACT_TYPE:
			raise ValueError("runtime_insert_contract_type must be korea_payroll_closing_review_audit_log_runtime_insert_v1")
	elif contract_type != SOURCE_CONTRACT_TYPE:
		raise ValueError("audit row contract_type must be korea_payroll_closing_review_audit_log_runtime_insert_v1")
	if row.get("source_audit_log_contract_type") != EXPECTED_AUDIT_LOG_CONTRACT_TYPE:
		raise ValueError("source_audit_log_contract_type must be korea_payroll_closing_draft_review_audit_log_v1")
	if row.get("runtime_action") != EXPECTED_RUNTIME_ACTION:
		raise ValueError("audit row runtime_action must be runtime_review_audit_log_created")
	if row.get("requires_runtime_apply") is not False:
		raise ValueError("audit row requires_runtime_apply must be false")
	if row.get("mutation_boundary") != EXPECTED_MUTATION_BOUNDARY:
		raise ValueError("audit row mutation_boundary must remain audit-log only")
	if row.get("doctype") != EXPECTED_DOCTYPE:
		raise ValueError("audit row doctype must be Korea Payroll Closing Review Audit Log")
	if row.get("docstatus") != 0:
		raise ValueError("audit row docstatus must be 0")
	if row.get("requires_human_approval") is not True:
		raise ValueError("audit row requires_human_approval must be true")
	if row.get("ai_role") != EXPECTED_AI_ROLE:
		raise ValueError("audit row ai_role must be assistant_only")

	action = _require_text(row.get("action"), "audit row action")
	if action not in _ALLOWED_ACTION_STATUSES:
		raise ValueError("audit row action must be approve_draft, reject_draft, or request_changes")
	status = _require_text(row.get("status"), "audit row status")
	if status != _ALLOWED_ACTION_STATUSES[action]:
		raise ValueError("audit row status must match action")
	previous_status = _require_text(row.get("previous_status"), "audit row previous_status")
	if previous_status != EXPECTED_PREVIOUS_STATUS:
		raise ValueError("previous_status must be draft_pending_human_approval")
	period_start = _parse_iso_date(row.get("period_start"), "period_start")
	period_end = _parse_iso_date(row.get("period_end"), "period_end")
	if period_start > period_end:
		raise ValueError("period_start must be on or before period_end")
	created_at = _parse_optional_iso_datetime(row.get("created_at", row.get("creation")), "created_at")
	return {
		"contract_type": contract_type,
		"name": _require_text(row.get("name"), "audit row name"),
		"draft_name": _require_text(row.get("draft_name"), "audit row draft_name"),
		"previous_status": previous_status,
		"status": status,
		"action": action,
		"review_actor": _require_text(row.get("review_actor"), "audit row review_actor"),
		"audit_actor": _require_text(row.get("audit_actor"), "audit row audit_actor"),
		"company": _require_text(row.get("company"), "audit row company"),
		"workplace": _require_text(row.get("workplace"), "audit row workplace"),
		"period_start": period_start.isoformat(),
		"period_end": period_end.isoformat(),
		"source_payroll_entry": _require_text(row.get("source_payroll_entry"), "audit row source_payroll_entry"),
		"created_at": created_at.isoformat() if created_at is not None else None,
		"sort_created_at": created_at.isoformat() if created_at is not None else "",
	}


def _normalize_workplaces(workplaces: list[str] | None) -> list[str] | None:
	if workplaces is None:
		return None
	if not isinstance(workplaces, list):
		raise ValueError("workplaces must be a list")
	normalized: list[str] = []
	for workplace in workplaces:
		text = _require_text(workplace, "workplaces[]")
		if text not in normalized:
			normalized.append(text)
	return normalized


def _require_text(value: Any, label: str) -> str:
	if not isinstance(value, str) or not value.strip():
		raise ValueError(f"{label} must be a non-empty string")
	return value.strip()


def _parse_iso_date(value: Any, label: str) -> dt.date:
	if not isinstance(value, str):
		raise ValueError(f"{label} must be an ISO date")
	try:
		return dt.date.fromisoformat(value)
	except ValueError as exc:
		raise ValueError(f"{label} must be an ISO date") from exc


def _parse_iso_datetime(value: Any, label: str) -> dt.datetime:
	if not isinstance(value, str):
		raise ValueError(f"{label} must be a timezone-aware ISO datetime")
	try:
		parsed = dt.datetime.fromisoformat(value)
	except ValueError as exc:
		raise ValueError(f"{label} must be a timezone-aware ISO datetime") from exc
	if parsed.tzinfo is None or parsed.utcoffset() is None:
		raise ValueError(f"{label} must be timezone-aware")
	return parsed


def _parse_optional_iso_datetime(value: Any, label: str) -> dt.datetime | None:
	if value is None:
		return None
	return _parse_iso_datetime(value, label)


def _reject_forbidden_score_keys(value: Any) -> None:
	for key, nested in _iter_json_items(value):
		normalized = _normalize_score_key(key)
		if any(fragment in normalized for fragment in _FORBIDDEN_SCORE_FRAGMENTS):
			raise ValueError("score keys are not allowed")
		if "risk" in normalized and isinstance(nested, (int, float)) and not isinstance(nested, bool):
			raise ValueError("numeric risk keys are not allowed")


def _iter_json_keys(value: Any):
	for key, _ in _iter_json_items(value):
		yield key


def _iter_json_items(value: Any):
	if isinstance(value, dict):
		for key, nested in value.items():
			if isinstance(key, str):
				yield key, nested
			yield from _iter_json_items(nested)
	elif isinstance(value, list):
		for item in value:
			yield from _iter_json_items(item)


def _normalize_score_key(key: str) -> str:
	return re.sub(r"[^a-z0-9]+", "_", key.strip().lower()).strip("_").replace("_", "")


__all__ = ["build_korea_payroll_review_audit_log_list"]
