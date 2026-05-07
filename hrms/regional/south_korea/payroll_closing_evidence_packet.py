"""Framework-free Korea payroll closing evidence packet contract.

This module turns an existing payroll closing session snapshot into a
human-review evidence packet for operator screens, runbooks, or export previews.
It intentionally performs no Frappe mutation, no provider calls, and no payroll
or legal numeric scoring. Human approval remains the final authority.
"""

from __future__ import annotations

import datetime as dt
import re
from copy import deepcopy
from typing import Any

SESSION_CONTRACT_TYPE = "korea_payroll_closing_session_v1"
CONTRACT_TYPE = "korea_payroll_closing_evidence_packet_v1"
AI_ROLE = "assistant_only"

_ALLOWED_NEXT_ACTIONS = {
	"review_attendance",
	"resolve_attendance_blockers",
	"assign_payroll_approver",
	"prepare_payroll_entry",
	"prepare_statutory_artifacts",
	"prepare_payslip_artifacts",
	"prepare_kakao_queue",
	"resolve_expense_settlements",
	"review_employment_contracts",
	"review_payroll_artifacts",
	"request_human_approval",
	"record_human_review",
}


_FORBIDDEN_SCORE_KEYS = {
	"risk_score",
	"riskscore",
	"risk-score",
	"legal_risk_score",
	"legalriskscore",
	"legal-risk-score",
	"probability",
	"probability_score",
	"probabilityscore",
	"probability-score",
	"success_rate",
	"successrate",
	"success-rate",
	"closing_success_rate",
	"closingsuccessrate",
	"closing-success-rate",
}
_FORBIDDEN_NORMALIZED_SCORE_FRAGMENTS = ("riskscore", "probability", "successrate")


def build_korea_payroll_closing_evidence_packet(
	session: dict[str, Any],
	*,
	actor: str,
	purpose: str = "payroll closing human review",
) -> dict[str, Any]:
	"""Build a side-effect-free evidence packet from a closing session.

	The packet is intentionally preview-only. It is a review bridge between the
	read model, operator UI, and later audit/draft persistence layers; it does not
	approve, close, save, submit, send, or call providers.
	"""

	if not isinstance(session, dict):
		raise ValueError("session must be a dict")
	actor_text = _require_text(actor, "actor")
	purpose_text = _require_text(purpose, "purpose")
	_validate_no_forbidden_scores(session)

	if session.get("contract_type") != SESSION_CONTRACT_TYPE:
		raise ValueError(f"session.contract_type must be {SESSION_CONTRACT_TYPE}")
	if session.get("requires_human_approval") is not True:
		raise ValueError("session.requires_human_approval must be true")
	if session.get("ai_role") != AI_ROLE:
		raise ValueError(f"session.ai_role must be {AI_ROLE}")

	company = _require_text(session.get("company"), "session.company")
	workplace = _require_text(session.get("workplace"), "session.workplace")
	period_start = _parse_iso_date(session.get("period_start"), "session.period_start")
	period_end = _parse_iso_date(session.get("period_end"), "session.period_end")
	if period_start > period_end:
		raise ValueError("session.period_start must be on or before session.period_end")
	period_start_text = period_start.isoformat()
	period_end_text = period_end.isoformat()
	status = _require_text(session.get("status"), "session.status")

	blockers = _require_list(session.get("blockers"), "session.blockers")
	next_actions = _require_list(session.get("next_actions"), "session.next_actions")
	readiness_cards = _require_list(session.get("readiness_cards"), "session.readiness_cards")
	payroll_artifacts = _require_dict(session.get("payroll_artifacts"), "session.payroll_artifacts")
	approval_state = _require_dict(session.get("approval_state"), "session.approval_state")
	notification_state = _require_dict(session.get("notification_state"), "session.notification_state")
	audit_preview = _require_dict(session.get("audit_preview"), "session.audit_preview")
	_validate_audit_preview_scope(
		audit_preview,
		company=company,
		workplace=workplace,
		period_start=period_start_text,
		period_end=period_end_text,
		status=status,
		blockers=blockers,
	)

	validated_next_actions = _validate_next_actions(next_actions)

	return {
		"contract_type": CONTRACT_TYPE,
		"source_session_contract_type": SESSION_CONTRACT_TYPE,
		"runtime_action": "preview_only",
		"requires_runtime_apply": False,
		"company": company,
		"workplace": workplace,
		"period_start": period_start_text,
		"period_end": period_end_text,
		"status": status,
		"actor": actor_text,
		"purpose": purpose_text,
		"blocker_codes": [_require_blocker_code(blocker, index) for index, blocker in enumerate(blockers)],
		"evidence_items": _build_evidence_items(
			readiness_cards=readiness_cards,
			payroll_artifacts=payroll_artifacts,
			approval_state=approval_state,
			notification_state=notification_state,
			expense_state=_optional_dict(session.get("expense_state"), "session.expense_state"),
			contract_state=_optional_dict(session.get("contract_state"), "session.contract_state"),
			audit_preview=audit_preview,
		),
		"review_checklist": _build_review_checklist(blockers),
		"next_actions": validated_next_actions,
		"source_session": deepcopy(session),
		"requires_human_approval": True,
		"ai_role": AI_ROLE,
	}


def _build_evidence_items(
	*,
	readiness_cards: list[Any],
	payroll_artifacts: dict[str, Any],
	approval_state: dict[str, Any],
	notification_state: dict[str, Any],
	expense_state: dict[str, Any],
	contract_state: dict[str, Any],
	audit_preview: dict[str, Any],
) -> list[dict[str, Any]]:
	return [
		{
			"key": "attendance",
			"label": "Attendance readiness",
			"summary": _summarize_readiness_card(readiness_cards, "attendance"),
		},
		{
			"key": "payroll_artifacts",
			"label": "Payroll and statutory artifacts",
			"summary": {
				"payroll_entry": payroll_artifacts.get("payroll_entry"),
				"salary_slip_count": payroll_artifacts.get("salary_slip_count"),
				"statutory_totals": deepcopy(payroll_artifacts.get("statutory_totals", {})),
			},
		},
		{
			"key": "approval",
			"label": "Approval readiness",
			"summary": deepcopy(approval_state),
		},
		{
			"key": "notification",
			"label": "Payslip/Kakao notification readiness",
			"summary": deepcopy(notification_state),
		},
		{
			"key": "expense_settlement",
			"label": "Expense settlement readiness",
			"summary": deepcopy(expense_state),
		},
		{
			"key": "employment_contracts",
			"label": "Employment contract readiness",
			"summary": deepcopy(contract_state),
		},
		{
			"key": "audit_preview",
			"label": "Audit preview boundary",
			"summary": deepcopy(audit_preview),
		},
	]


def _build_review_checklist(blockers: list[Any]) -> list[dict[str, Any]]:
	if not blockers:
		return [{"status": "needs_human_approval", "action": "record_human_review", "requires_runtime_apply": True}]
	checklist = []
	for index, blocker in enumerate(blockers):
		if not isinstance(blocker, dict):
			raise ValueError(f"session.blockers[{index}] must be a dict")
		code = _require_blocker_code(blocker, index)
		checklist.append(
			{
				"status": "needs_human_review",
				"blocker_code": code,
				"message": _optional_text(blocker.get("message")) or code,
				"requires_runtime_apply": True,
			}
		)
	return checklist


def _summarize_readiness_card(readiness_cards: list[Any], key: str) -> dict[str, Any]:
	for index, card in enumerate(readiness_cards):
		if not isinstance(card, dict):
			raise ValueError(f"session.readiness_cards[{index}] must be a dict")
		if card.get("key") == key:
			return deepcopy(card)
	return {"key": key, "status": "missing"}


def _validate_next_actions(actions: list[Any]) -> list[dict[str, Any]]:
	validated = []
	for index, action in enumerate(actions):
		if not isinstance(action, dict):
			raise ValueError(f"session.next_actions[{index}] must be a dict")
		action_name = _require_text(action.get("action"), f"session.next_actions[{index}].action")
		if action_name not in _ALLOWED_NEXT_ACTIONS:
			raise ValueError(f"session.next_actions[{index}].action is not allowed")
		if "requires_runtime_apply" in action and not isinstance(action["requires_runtime_apply"], bool):
			raise ValueError(f"session.next_actions[{index}].requires_runtime_apply must be a bool")
		validated.append(deepcopy(action))
	return validated



def _validate_audit_preview_scope(
	audit_preview: dict[str, Any],
	*,
	company: str,
	workplace: str,
	period_start: str,
	period_end: str,
	status: str,
	blockers: list[Any],
) -> None:
	if audit_preview.get("runtime_action") != "preview_only":
		raise ValueError("session.audit_preview.runtime_action must be preview_only")
	if audit_preview.get("requires_runtime_apply") is not True:
		raise ValueError("session.audit_preview.requires_runtime_apply must be true")
	for field, expected in [
		("company", company),
		("workplace", workplace),
		("period_start", period_start),
		("period_end", period_end),
		("status", status),
	]:
		if audit_preview.get(field) != expected:
			raise ValueError(f"session.audit_preview.{field} must match session.{field}")
	expected_codes = [_require_blocker_code(blocker, index) for index, blocker in enumerate(blockers)]
	if audit_preview.get("blocker_codes") != expected_codes:
		raise ValueError("session.audit_preview.blocker_codes must match session.blockers")


def _validate_no_forbidden_scores(value: Any) -> None:
	if isinstance(value, dict):
		for key, nested in value.items():
			if _is_forbidden_score_key(key):
				raise ValueError(f"{key} is not allowed in payroll closing evidence packets")
			_validate_no_forbidden_scores(nested)
	elif isinstance(value, list):
		for item in value:
			_validate_no_forbidden_scores(item)


def _is_forbidden_score_key(key: Any) -> bool:
	if not isinstance(key, str):
		return False
	normalized = re.sub(r"[^a-z0-9]", "", key.lower())
	return normalized in _FORBIDDEN_SCORE_KEYS or any(fragment in normalized for fragment in _FORBIDDEN_NORMALIZED_SCORE_FRAGMENTS)


def _require_blocker_code(blocker: Any, index: int) -> str:
	if not isinstance(blocker, dict):
		raise ValueError(f"session.blockers[{index}] must be a dict")
	return _require_text(blocker.get("code"), f"session.blockers[{index}].code")


def _require_dict(value: Any, label: str) -> dict[str, Any]:
	if not isinstance(value, dict):
		raise ValueError(f"{label} must be a dict")
	return value


def _optional_dict(value: Any, label: str) -> dict[str, Any]:
	if value is None:
		return {}
	if not isinstance(value, dict):
		raise ValueError(f"{label} must be a dict")
	return value


def _require_list(value: Any, label: str) -> list[Any]:
	if not isinstance(value, list):
		raise ValueError(f"{label} must be a list")
	return value


def _require_text(value: Any, label: str) -> str:
	if not isinstance(value, str) or not value.strip():
		raise ValueError(f"{label} must be a non-empty string")
	return value.strip()


def _optional_text(value: Any) -> str | None:
	if value is None:
		return None
	if isinstance(value, str) and value.strip():
		return value.strip()
	return None


def _parse_iso_date(value: Any, label: str) -> dt.date:
	if not isinstance(value, str):
		raise ValueError(f"{label} must be an ISO date")
	try:
		return dt.date.fromisoformat(value)
	except ValueError as exc:
		raise ValueError(f"{label} must be an ISO date") from exc
