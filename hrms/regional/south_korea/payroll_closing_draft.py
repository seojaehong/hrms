"""Framework-free Korea payroll closing runtime draft contract.

This module is the first persistence-boundary bridge after the preview-only
payroll closing session read model. It builds a reviewable draft payload that a
later Frappe adapter can create as a draft document, but this helper itself does
not save, submit, approve, send, or call providers.
"""

from __future__ import annotations

import datetime as dt
import re
from copy import deepcopy
from typing import Any


SESSION_CONTRACT_TYPE = "korea_payroll_closing_session_v1"
DRAFT_CONTRACT_TYPE = "korea_payroll_closing_draft_v1"
AI_ROLE = "assistant_only"


def build_korea_payroll_closing_draft(session: dict[str, Any], *, actor: str) -> dict[str, Any]:
	"""Build a draft-document payload from a review-ready payroll closing session.

	The output is a side-effect-free contract for a future runtime adapter. It
	requires an already review-ready session and preserves the human-approval / AI
	assistant-only guardrails before exposing a draft creation boundary.
	"""

	if not isinstance(session, dict):
		raise ValueError("session must be a dict")
	actor_text = _require_string_text(actor, "actor")
	if session.get("contract_type") != SESSION_CONTRACT_TYPE:
		raise ValueError(f"session.contract_type must be {SESSION_CONTRACT_TYPE}")
	if session.get("requires_human_approval") is not True:
		raise ValueError("session.requires_human_approval must be true")
	if session.get("ai_role") != AI_ROLE:
		raise ValueError(f"session.ai_role must be {AI_ROLE}")
	if session.get("status") != "review_ready":
		raise ValueError("session.status must be review_ready")
	_forbid_numeric_score_fields(session)
	blockers = session.get("blockers")
	if blockers != []:
		raise ValueError("session.blockers must be empty for draft creation")

	company = _require_string_text(session.get("company"), "session.company")
	workplace = _require_string_text(session.get("workplace"), "session.workplace")
	period_start = _parse_iso_date_text(session.get("period_start"), "session.period_start")
	period_end = _parse_iso_date_text(session.get("period_end"), "session.period_end")
	if dt.date.fromisoformat(period_start) > dt.date.fromisoformat(period_end):
		raise ValueError("session.period_start must be on or before session.period_end")
	payroll_artifacts = _require_dict(session.get("payroll_artifacts"), "session.payroll_artifacts")
	payroll_entry_value = payroll_artifacts.get("payroll_entry")
	if not isinstance(payroll_entry_value, str) or not payroll_entry_value.strip():
		raise ValueError("session.payroll_artifacts.payroll_entry is required")
	payroll_entry = payroll_entry_value.strip()
	approval_state = _require_dict(session.get("approval_state"), "session.approval_state")
	approver = _require_string_text(approval_state.get("approver"), "session.approval_state.approver")
	audit_preview = _require_dict(session.get("audit_preview"), "session.audit_preview")
	if audit_preview.get("event_type") != "korea_payroll_closing_session_review_v1":
		raise ValueError("session.audit_preview.event_type must be korea_payroll_closing_session_review_v1")
	_validate_audit_preview(
		audit_preview,
		company=company,
		workplace=workplace,
		period_start=period_start,
		period_end=period_end,
	)

	payload = {
		"session": _safe_session_snapshot(session),
		"payroll_artifacts": deepcopy(payroll_artifacts),
		"approval_state": deepcopy(approval_state),
		"notification_state": deepcopy(_require_dict(session.get("notification_state"), "session.notification_state")),
		"readiness_cards": deepcopy(_require_list(session.get("readiness_cards"), "session.readiness_cards")),
		"next_actions": deepcopy(_require_list(session.get("next_actions"), "session.next_actions")),
		"audit_preview": deepcopy(audit_preview),
	}

	return {
		"contract_type": DRAFT_CONTRACT_TYPE,
		"doctype": "Korea Payroll Closing Draft",
		"runtime_action": "create_draft",
		"requires_runtime_apply": True,
		"mutation_boundary": "draft_only_no_submit_no_approve_no_send",
		"company": company,
		"workplace": workplace,
		"period_start": period_start,
		"period_end": period_end,
		"status": "draft_pending_human_approval",
		"source_session_contract_type": SESSION_CONTRACT_TYPE,
		"source_payroll_entry": payroll_entry,
		"approver": approver,
		"actor": actor_text,
		"payload": payload,
		"requires_human_approval": True,
		"ai_role": AI_ROLE,
	}


def _safe_session_snapshot(session: dict[str, Any]) -> dict[str, Any]:
	return {
		"contract_type": session.get("contract_type"),
		"company": session.get("company"),
		"workplace": session.get("workplace"),
		"period_start": session.get("period_start"),
		"period_end": session.get("period_end"),
		"status": session.get("status"),
		"blockers": deepcopy(session.get("blockers")),
		"requires_human_approval": session.get("requires_human_approval"),
		"ai_role": session.get("ai_role"),
	}


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


def _validate_audit_preview(
	audit_preview: dict[str, Any],
	*,
	company: str,
	workplace: str,
	period_start: str,
	period_end: str,
) -> None:
	if audit_preview.get("runtime_action") != "preview_only":
		raise ValueError("session.audit_preview.runtime_action must be preview_only")
	if audit_preview.get("requires_runtime_apply") is not True:
		raise ValueError("session.audit_preview.requires_runtime_apply must be true")
	if audit_preview.get("blocker_codes") != []:
		raise ValueError("session.audit_preview.blocker_codes must be empty")
	for key, expected in {
		"company": company,
		"workplace": workplace,
		"period_start": period_start,
		"period_end": period_end,
		"status": "review_ready",
	}.items():
		if audit_preview.get(key) != expected:
			raise ValueError(f"session.audit_preview.{key} must match session.{key}")


_FORBIDDEN_SCORE_KEYS = {"risk_score", "probability", "success_rate", "legal_risk_score"}
_FORBIDDEN_SCORE_KEY_FRAGMENTS = ("risk_score", "probability", "success_rate")
_FORBIDDEN_NORMALIZED_SCORE_FRAGMENTS = ("riskscore", "probability", "successrate")


def _forbid_numeric_score_fields(value: Any) -> None:
	if isinstance(value, dict):
		for key, nested in value.items():
			if _is_forbidden_score_key(key):
				raise ValueError(f"{key} is not allowed in payroll closing draft payloads")
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


def _require_dict(value: Any, fieldname: str) -> dict[str, Any]:
	if not isinstance(value, dict):
		raise ValueError(f"{fieldname} must be a dict")
	return value


def _require_list(value: Any, fieldname: str) -> list[Any]:
	if not isinstance(value, list):
		raise ValueError(f"{fieldname} must be a list")
	return value


__all__ = ["build_korea_payroll_closing_draft"]
