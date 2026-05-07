"""Framework-free Korea payroll closing draft runtime-apply preflight.

This module converts a validated ``korea_payroll_closing_draft_v1`` payload into
an explicit document-creation plan for a later Frappe adapter. It is still
side-effect-free: no save, submit, approval, notification, provider call, or
runtime lookup happens here.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from copy import deepcopy
from typing import Any

DRAFT_CONTRACT_TYPE = "korea_payroll_closing_draft_v1"
SESSION_CONTRACT_TYPE = "korea_payroll_closing_session_v1"
APPLY_PLAN_CONTRACT_TYPE = "korea_payroll_closing_draft_apply_plan_v1"
AI_ROLE = "assistant_only"
DRAFT_DOCTYPE = "Korea Payroll Closing Draft"
MUTATION_BOUNDARY = "draft_only_no_submit_no_approve_no_send"


def build_korea_payroll_closing_draft_apply_plan(draft: dict[str, Any], *, actor: str) -> dict[str, Any]:
	"""Build a no-mutation runtime draft-creation plan from a draft contract."""

	if not isinstance(draft, dict):
		raise ValueError("draft must be a dict")
	actor_text = _require_string_text(actor, "actor")
	_forbid_numeric_score_fields(draft)

	if draft.get("contract_type") != DRAFT_CONTRACT_TYPE:
		raise ValueError(f"draft.contract_type must be {DRAFT_CONTRACT_TYPE}")
	if draft.get("doctype") != DRAFT_DOCTYPE:
		raise ValueError(f"draft.doctype must be {DRAFT_DOCTYPE}")
	if draft.get("runtime_action") != "create_draft":
		raise ValueError("draft.runtime_action must be create_draft")
	if draft.get("requires_runtime_apply") is not True:
		raise ValueError("draft.requires_runtime_apply must be true")
	if draft.get("mutation_boundary") != MUTATION_BOUNDARY:
		raise ValueError(f"draft.mutation_boundary must be {MUTATION_BOUNDARY}")
	if draft.get("status") != "draft_pending_human_approval":
		raise ValueError("draft.status must be draft_pending_human_approval")
	if draft.get("requires_human_approval") is not True:
		raise ValueError("draft.requires_human_approval must be true")
	if draft.get("ai_role") != AI_ROLE:
		raise ValueError(f"draft.ai_role must be {AI_ROLE}")

	company = _require_string_text(draft.get("company"), "draft.company")
	workplace = _require_string_text(draft.get("workplace"), "draft.workplace")
	period_start = _parse_iso_date_text(draft.get("period_start"), "draft.period_start")
	period_end = _parse_iso_date_text(draft.get("period_end"), "draft.period_end")
	if dt.date.fromisoformat(period_start) > dt.date.fromisoformat(period_end):
		raise ValueError("draft.period_start must be on or before draft.period_end")
	source_payroll_entry = _require_string_text(draft.get("source_payroll_entry"), "draft.source_payroll_entry")
	approver = _require_string_text(draft.get("approver"), "draft.approver")
	source_session_contract_type = _require_string_text(
		draft.get("source_session_contract_type"), "draft.source_session_contract_type"
	)
	if source_session_contract_type != SESSION_CONTRACT_TYPE:
		raise ValueError(f"draft.source_session_contract_type must be {SESSION_CONTRACT_TYPE}")
	payload = _require_dict(draft.get("payload"), "draft.payload")
	_validate_payload_scope(payload, company=company, workplace=workplace, period_start=period_start, period_end=period_end)
	_validate_review_checklist(payload.get("review_checklist"))
	audit_preview = _require_dict(payload.get("audit_preview"), "draft.payload.audit_preview")
	_validate_audit_preview_scope(
		audit_preview,
		company=company,
		workplace=workplace,
		period_start=period_start,
		period_end=period_end,
	)

	field_values = {
		"company": company,
		"workplace": workplace,
		"period_start": period_start,
		"period_end": period_end,
		"status": "draft_pending_human_approval",
		"source_payroll_entry": source_payroll_entry,
		"approver": approver,
		"source_session_contract_type": source_session_contract_type,
		"payload": deepcopy(payload),
		"audit_preview": deepcopy(audit_preview),
	}
	doctype_insert_preview = {
		"doctype": DRAFT_DOCTYPE,
		"runtime_action": "preview_only",
		"requires_runtime_apply": True,
		"mutation_boundary": MUTATION_BOUNDARY,
		"fields": {
			"docstatus": 0,
			"company": company,
			"workplace": workplace,
			"period_start": period_start,
			"period_end": period_end,
			"status": "draft_pending_human_approval",
			"source_payroll_entry": source_payroll_entry,
			"approver": approver,
			"source_session_contract_type": source_session_contract_type,
			"mutation_boundary": MUTATION_BOUNDARY,
			"requires_human_approval": 1,
			"ai_role": AI_ROLE,
			"payload": _json_dumps(payload),
			"audit_preview": _json_dumps(audit_preview),
		},
	}

	return {
		"contract_type": APPLY_PLAN_CONTRACT_TYPE,
		"source_draft_contract_type": DRAFT_CONTRACT_TYPE,
		"runtime_action": "preview_runtime_draft_apply",
		"requires_runtime_apply": True,
		"mutation_boundary": MUTATION_BOUNDARY,
		"would_create_doctype": DRAFT_DOCTYPE,
		"docstatus": 0,
		"status": "draft_pending_human_approval",
		"company": company,
		"workplace": workplace,
		"period_start": period_start,
		"period_end": period_end,
		"source_payroll_entry": source_payroll_entry,
		"approver": approver,
		"actor": actor_text,
		"field_values": field_values,
		"doctype_insert_preview": doctype_insert_preview,
		"requires_human_approval": True,
		"ai_role": AI_ROLE,
	}


def _validate_payload_scope(
	payload: dict[str, Any],
	*,
	company: str,
	workplace: str,
	period_start: str,
	period_end: str,
) -> None:
	session = _require_dict(payload.get("session"), "draft.payload.session")
	if session.get("contract_type") != SESSION_CONTRACT_TYPE:
		raise ValueError(f"draft.payload.session.contract_type must be {SESSION_CONTRACT_TYPE}")
	for key, expected in {
		"company": company,
		"workplace": workplace,
		"period_start": period_start,
		"period_end": period_end,
	}.items():
		if session.get(key) != expected:
			raise ValueError(f"draft.payload.session.{key} must match draft.{key}")
	if session.get("status") != "review_ready":
		raise ValueError("draft.payload.session.status must be review_ready")
	if session.get("blockers") != []:
		raise ValueError("draft.payload.session.blockers must be empty")
	if session.get("requires_human_approval") is not True:
		raise ValueError("draft.payload.session.requires_human_approval must be true")
	if session.get("ai_role") != AI_ROLE:
		raise ValueError(f"draft.payload.session.ai_role must be {AI_ROLE}")


def _validate_audit_preview_scope(
	audit_preview: dict[str, Any],
	*,
	company: str,
	workplace: str,
	period_start: str,
	period_end: str,
) -> None:
	if audit_preview.get("runtime_action") != "preview_only":
		raise ValueError("draft.payload.audit_preview.runtime_action must be preview_only")
	for key, expected in {
		"company": company,
		"workplace": workplace,
		"period_start": period_start,
		"period_end": period_end,
	}.items():
		if audit_preview.get(key) != expected:
			raise ValueError(f"draft.payload.audit_preview.{key} must match draft.{key}")


def _validate_review_checklist(value: Any) -> None:
	items = _require_list(value, "draft.payload.review_checklist")
	if not items:
		raise ValueError("draft.payload.review_checklist must include at least one item")
	for item in items:
		if not isinstance(item, dict):
			raise ValueError("draft.payload.review_checklist must contain dict items")
		_require_string_text(item.get("key"), "draft.payload.review_checklist.key")
		if item.get("checked") is not True:
			raise ValueError("draft.payload.review_checklist.checked must be a boolean true")
		if item.get("requires_human_review") is not True:
			raise ValueError("draft.payload.review_checklist.requires_human_review must be true")
		if item.get("ai_role") != AI_ROLE:
			raise ValueError(f"draft.payload.review_checklist.ai_role must be {AI_ROLE}")


def _require_string_text(value: Any, fieldname: str) -> str:
	if not isinstance(value, str) or not value.strip():
		raise ValueError(f"{fieldname} must be a non-empty string")
	return value.strip()


def _parse_iso_date_text(value: Any, fieldname: str) -> str:
	text = _require_string_text(value, fieldname)
	try:
		parsed = dt.date.fromisoformat(text)
	except ValueError as exc:
		raise ValueError(f"{fieldname} must be an ISO date") from exc
	return parsed.isoformat()


def _require_dict(value: Any, fieldname: str) -> dict[str, Any]:
	if not isinstance(value, dict):
		raise ValueError(f"{fieldname} must be a dict")
	return value


def _require_list(value: Any, fieldname: str) -> list[Any]:
	if not isinstance(value, list):
		raise ValueError(f"{fieldname} must be a list")
	return value


def _json_dumps(value: dict[str, Any]) -> str:
	return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


_FORBIDDEN_SCORE_KEYS = {"risk_score", "probability", "success_rate", "legal_risk_score"}
_FORBIDDEN_SCORE_KEY_FRAGMENTS = ("risk_score", "probability", "success_rate")
_FORBIDDEN_NORMALIZED_SCORE_FRAGMENTS = ("riskscore", "probability", "successrate")


def _forbid_numeric_score_fields(value: Any) -> None:
	if isinstance(value, dict):
		for key, nested in value.items():
			if _is_forbidden_score_key(key):
				raise ValueError(f"{key} is not allowed in payroll closing draft apply payloads")
			_forbid_numeric_score_fields(nested)
	elif isinstance(value, list):
		for item in value:
			_forbid_numeric_score_fields(item)


def _is_forbidden_score_key(key: Any) -> bool:
	if not isinstance(key, str):
		return False
	normalized = re.sub(r"[^a-z0-9]", "", key.lower())
	return (
		key in _FORBIDDEN_SCORE_KEYS
		or any(fragment in key for fragment in _FORBIDDEN_SCORE_KEY_FRAGMENTS)
		or any(fragment in normalized for fragment in _FORBIDDEN_NORMALIZED_SCORE_FRAGMENTS)
	)


__all__ = ["build_korea_payroll_closing_draft_apply_plan"]
