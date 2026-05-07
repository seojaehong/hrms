"""Framework-free Korea payroll closing session read model.

This module composes existing preview/helper outputs into one operator-facing
payroll-closing session snapshot. It intentionally avoids Frappe imports,
persistence, provider calls, and legal/probability scoring. Runtime adapters can
later persist or mutate from this read model behind human approval.
"""

from __future__ import annotations

import datetime as dt
import re
from copy import deepcopy
from typing import Any


CONTRACT_TYPE = "korea_payroll_closing_session_v1"
AI_ROLE = "assistant_only"


def build_korea_payroll_closing_session(
	*,
	company: str,
	workplace: str,
	period_start: str | dt.date,
	period_end: str | dt.date,
	attendance_summary: dict[str, Any] | None,
	payroll_entry: dict[str, Any] | None,
	approval_state: dict[str, Any] | None,
	notification_state: dict[str, Any] | None,
	expense_state: dict[str, Any] | None = None,
	contract_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
	"""Build a payroll-closing session read model for one workplace/month.

	The returned contract is side-effect-free: it does not save, submit, approve,
	queue, send, or call providers. It fails closed on cross-company/workplace or
	period mismatches and surfaces operational blockers for human review.
	"""

	company = _require_text(company, "company")
	workplace = _require_text(workplace, "workplace")
	period_start_date = _parse_iso_date(period_start, "period_start")
	period_end_date = _parse_iso_date(period_end, "period_end")
	if period_start_date > period_end_date:
		raise ValueError("period_start must be on or before period_end")
	period_start_text = period_start_date.isoformat()
	period_end_text = period_end_date.isoformat()

	attendance_state = _normalize_attendance_state(
		_optional_payload(attendance_summary, "attendance_summary"),
		company=company,
		workplace=workplace,
		period_start=period_start_text,
		period_end=period_end_text,
	)
	payroll_artifacts = _normalize_payroll_artifacts(
		_optional_payload(payroll_entry, "payroll_entry"),
		company=company,
		workplace=workplace,
		period_start=period_start_text,
		period_end=period_end_text,
	)
	approval = _normalize_approval_state(
		_optional_payload(approval_state, "approval_state"),
		company=company,
		workplace=workplace,
		period_start=period_start_text,
		period_end=period_end_text,
	)
	notifications = _normalize_notification_state(
		_optional_payload(notification_state, "notification_state"),
		company=company,
		workplace=workplace,
		period_start=period_start_text,
		period_end=period_end_text,
	)
	expenses = _normalize_expense_state(
		_optional_payload(expense_state, "expense_state"),
		company=company,
		workplace=workplace,
		period_start=period_start_text,
		period_end=period_end_text,
	)
	contracts = _normalize_contract_state(
		_optional_payload(contract_state, "contract_state"),
		company=company,
		workplace=workplace,
		period_start=period_start_text,
		period_end=period_end_text,
	)

	blockers: list[dict[str, Any]] = []
	if not attendance_state["ready"]:
		blockers.append(
			{
				"code": "attendance_not_ready",
				"severity": "blocking",
				"message": "Attendance must be reviewed before payroll closing.",
				"details": {"unmarked_days": deepcopy(attendance_state["unmarked_days"])},
			}
		)
	if not approval["approver"]:
		blockers.append(
			{
				"code": "approver_missing",
				"severity": "blocking",
				"message": "A payroll closing approver must be assigned before final review.",
			}
		)
	if not payroll_artifacts["payroll_entry"]:
		blockers.append(
			{
				"code": "payroll_entry_missing",
				"severity": "blocking",
				"message": "Payroll Entry artifact is required for closing review.",
			}
		)
	if not payroll_artifacts["statutory_totals"]:
		blockers.append(
			{
				"code": "statutory_artifacts_missing",
				"severity": "blocking",
				"message": "Statutory payroll totals are required for closing review.",
			}
		)
	if not notifications["payslip_artifacts_ready"]:
		blockers.append(
			{
				"code": "payslip_artifacts_missing",
				"severity": "blocking",
				"message": "Payslip artifacts must be prepared before employee notification.",
			}
		)
	if not notifications["kakao_queue_ready"]:
		blockers.append(
			{
				"code": "kakao_queue_not_ready",
				"severity": "blocking",
				"message": "Kakao notification queue readiness must be confirmed before closing.",
			}
		)
	if not expenses["settlement_ready"]:
		blockers.append(
			{
				"code": "expense_settlement_not_ready",
				"severity": "blocking",
				"message": "Expense settlements must be reviewed before payroll closing.",
				"details": {
					"open_claim_count": expenses["open_claim_count"],
					"approved_unpaid_count": expenses["approved_unpaid_count"],
				},
			}
		)
	if not contracts["ready"]:
		blockers.append(
			{
				"code": "employment_contracts_not_ready",
				"severity": "blocking",
				"message": "Employment contract artifacts must be reviewed before payroll closing.",
				"details": {
					"missing_contract_count": contracts["missing_contract_count"],
					"stale_contract_count": contracts["stale_contract_count"],
				},
			}
		)

	status = "blocked" if blockers else "review_ready"
	if status == "review_ready":
		for label, source in [
			("attendance_summary", attendance_summary),
			("payroll_entry", payroll_entry),
			("approval_state", approval_state),
			("notification_state", notification_state),
		]:
			scoped_source = _optional_payload(source, label)
			_require_explicit_scope(scoped_source, label=label)
			_require_explicit_period(scoped_source, label=label)
		for label, source in [("expense_state", expense_state), ("contract_state", contract_state)]:
			scoped_source = _optional_payload(source, label)
			if scoped_source:
				_require_explicit_scope(scoped_source, label=label)
				_require_explicit_period(scoped_source, label=label)
	return {
		"contract_type": CONTRACT_TYPE,
		"company": company,
		"workplace": workplace,
		"period_start": period_start_text,
		"period_end": period_end_text,
		"status": status,
		"blockers": blockers,
		"next_actions": _build_next_actions(blockers),
		"readiness_cards": _build_readiness_cards(
			attendance_state=attendance_state,
			payroll_artifacts=payroll_artifacts,
			approval_state=approval,
			notification_state=notifications,
			expense_state=expenses,
			contract_state=contracts,
		),
		"review_checklist": _build_review_checklist(),
		"payroll_artifacts": payroll_artifacts,
		"approval_state": approval,
		"notification_state": notifications,
		"expense_state": expenses,
		"contract_state": contracts,
		"audit_preview": {
			"event_type": "korea_payroll_closing_session_review_v1",
			"runtime_action": "preview_only",
			"requires_runtime_apply": True,
			"company": company,
			"workplace": workplace,
			"period_start": period_start_text,
			"period_end": period_end_text,
			"status": status,
			"blocker_codes": [blocker["code"] for blocker in blockers],
		},
		"requires_human_approval": True,
		"ai_role": AI_ROLE,
	}


_ALLOWED_AUDIT_ACTIONS = {"review_blockers", "request_human_approval", "record_human_review"}
_ALLOWED_SESSION_BLOCKER_CODES = {
	"attendance_not_ready",
	"approver_missing",
	"payroll_entry_missing",
	"statutory_artifacts_missing",
	"payslip_artifacts_missing",
	"kakao_queue_not_ready",
	"expense_settlement_not_ready",
	"employment_contracts_not_ready",
}


def build_korea_payroll_closing_audit_event(
	session: dict[str, Any],
	*,
	actor: str,
	action: str,
	note: str | None = None,
) -> dict[str, Any]:
	"""Build a side-effect-free audit event preview for a closing session.

	This function creates a runtime-ready payload that a later Frappe adapter can
	persist as an audit log. It does not approve, close, save, submit, or send
	anything; payroll-sensitive decisions remain human-approved.
	"""

	if not isinstance(session, dict):
		raise ValueError("session must be a dict")
	if session.get("contract_type") != CONTRACT_TYPE:
		raise ValueError(f"session.contract_type must be {CONTRACT_TYPE}")
	if session.get("requires_human_approval") is not True:
		raise ValueError("session.requires_human_approval must be true")
	if session.get("ai_role") != AI_ROLE:
		raise ValueError(f"session.ai_role must be {AI_ROLE}")

	actor_text = _require_string_text(actor, "actor")
	action_text = _require_string_text(action, "action")
	if action_text not in _ALLOWED_AUDIT_ACTIONS:
		allowed = ", ".join(sorted(_ALLOWED_AUDIT_ACTIONS))
		raise ValueError(f"action must be one of: {allowed}")
	if "blockers" not in session:
		raise ValueError("session.blockers is required")
	blockers = session.get("blockers")
	if not isinstance(blockers, list):
		raise ValueError("session.blockers must be a list")
	blocker_codes = []
	for blocker in blockers:
		if not isinstance(blocker, dict):
			raise ValueError("session.blockers must contain dict items")
		code = blocker.get("code")
		if not isinstance(code, str):
			raise ValueError("session.blockers.code must be a string")
		code_text = code.strip()
		if not code_text:
			raise ValueError("session.blockers.code is required")
		if code != code_text or code_text not in _ALLOWED_SESSION_BLOCKER_CODES:
			raise ValueError("session.blockers.code must be a known blocker code")
		blocker_codes.append(code_text)
	note_text = _optional_note(note)

	return {
		"contract_type": "korea_payroll_closing_audit_event_v1",
		"session_contract_type": CONTRACT_TYPE,
		"company": _require_text(session.get("company"), "session.company"),
		"workplace": _require_text(session.get("workplace"), "session.workplace"),
		"period_start": _parse_iso_date(session.get("period_start"), "session.period_start").isoformat(),
		"period_end": _parse_iso_date(session.get("period_end"), "session.period_end").isoformat(),
		"session_status": _require_text(session.get("status"), "session.status"),
		"action": action_text,
		"actor": actor_text,
		"note": note_text,
		"blocker_codes": blocker_codes,
		"runtime_action": "preview_only",
		"requires_runtime_apply": True,
		"requires_human_approval": True,
		"ai_role": AI_ROLE,
	}


def _normalize_attendance_state(
	attendance_summary: dict[str, Any],
	*,
	company: str,
	workplace: str,
	period_start: str,
	period_end: str,
) -> dict[str, Any]:
	_validate_optional_scope(attendance_summary, company=company, workplace=workplace, label="attendance_summary")
	_validate_optional_period(attendance_summary, period_start=period_start, period_end=period_end, label="attendance_summary")
	unmarked_days = list(attendance_summary.get("unmarked_days") or [])
	status = str(attendance_summary.get("status") or "").strip().lower()
	ready = status in {"ready", "closed", "reviewed"} and not unmarked_days
	return {
		"ready": ready,
		"status": status or "unknown",
		"employee_count": _optional_int(attendance_summary.get("employee_count")),
		"unmarked_days": [str(day) for day in unmarked_days],
	}


def _normalize_payroll_artifacts(
	payroll_entry: dict[str, Any],
	*,
	company: str,
	workplace: str,
	period_start: str,
	period_end: str,
) -> dict[str, Any]:
	_validate_optional_scope(payroll_entry, company=company, workplace=workplace, label="payroll_entry")
	_validate_optional_period(payroll_entry, period_start=period_start, period_end=period_end, label="payroll_entry")
	salary_slips = payroll_entry.get("salary_slips") or []
	if not isinstance(salary_slips, list):
		raise ValueError("payroll_entry.salary_slips must be a list")
	included_slips = []
	for slip in salary_slips:
		if not isinstance(slip, dict):
			raise ValueError("salary_slips must contain dict items")
		_validate_optional_scope(slip, company=company, workplace=workplace, label="salary_slip")
		_validate_optional_period(slip, period_start=period_start, period_end=period_end, label="salary_slip")
		included_slips.append(
			{
				"name": str(slip.get("name") or "").strip() or None,
				"employee": str(slip.get("employee") or "").strip() or None,
				"status": str(slip.get("status") or "").strip() or None,
			}
		)
	statutory_payload = payroll_entry.get("statutory_batch_payload") or payroll_entry.get("statutory_batch") or {}
	statutory_totals = {}
	if isinstance(statutory_payload, dict):
		statutory_totals = deepcopy(statutory_payload.get("totals") or {})
	else:
		raise ValueError("payroll_entry.statutory_batch_payload must be a dict")
	return {
		"payroll_entry": str(payroll_entry.get("name") or "").strip() or None,
		"salary_slip_count": len(included_slips),
		"salary_slips": included_slips,
		"statutory_totals": statutory_totals,
		"requires_runtime_apply": True,
	}


def _normalize_approval_state(
	approval_state: dict[str, Any],
	*,
	company: str,
	workplace: str,
	period_start: str,
	period_end: str,
) -> dict[str, Any]:
	_validate_optional_scope(approval_state, company=company, workplace=workplace, label="approval_state")
	_validate_optional_period(approval_state, period_start=period_start, period_end=period_end, label="approval_state")
	approver = str(approval_state.get("approver") or "").strip() or None
	return {
		"approver": approver,
		"status": str(approval_state.get("status") or "pending_review").strip(),
		"open_items": _optional_int(approval_state.get("open_items")),
		"requires_human_approval": True,
	}


def _normalize_notification_state(
	notification_state: dict[str, Any],
	*,
	company: str,
	workplace: str,
	period_start: str,
	period_end: str,
) -> dict[str, Any]:
	_validate_optional_scope(notification_state, company=company, workplace=workplace, label="notification_state")
	_validate_optional_period(notification_state, period_start=period_start, period_end=period_end, label="notification_state")
	payslip_artifacts_ready = _optional_bool(
		notification_state.get("payslip_artifacts_ready"), "notification_state.payslip_artifacts_ready"
	)
	kakao_queue_ready = _optional_bool(notification_state.get("kakao_queue_ready"), "notification_state.kakao_queue_ready")
	return {
		"payslip_artifacts_ready": payslip_artifacts_ready,
		"kakao_queue_ready": kakao_queue_ready,
		"recipient_count": _optional_int(notification_state.get("recipient_count")),
		"requires_runtime_send": kakao_queue_ready,
	}


def _normalize_expense_state(
	expense_state: dict[str, Any],
	*,
	company: str,
	workplace: str,
	period_start: str,
	period_end: str,
) -> dict[str, Any]:
	_validate_optional_scope(expense_state, company=company, workplace=workplace, label="expense_state")
	_validate_optional_period(expense_state, period_start=period_start, period_end=period_end, label="expense_state")
	if not expense_state:
		return {
			"settlement_ready": True,
			"open_claim_count": 0,
			"approved_unpaid_count": 0,
			"requires_runtime_apply": False,
		}
	return {
		"settlement_ready": _optional_bool(expense_state.get("settlement_ready"), "expense_state.settlement_ready"),
		"open_claim_count": _optional_int(expense_state.get("open_claim_count")) or 0,
		"approved_unpaid_count": _optional_int(expense_state.get("approved_unpaid_count")) or 0,
		"requires_runtime_apply": False,
	}


def _normalize_contract_state(
	contract_state: dict[str, Any],
	*,
	company: str,
	workplace: str,
	period_start: str,
	period_end: str,
) -> dict[str, Any]:
	_validate_optional_scope(contract_state, company=company, workplace=workplace, label="contract_state")
	_validate_optional_period(contract_state, period_start=period_start, period_end=period_end, label="contract_state")
	if not contract_state:
		return {
			"ready": True,
			"contracts_reviewed": True,
			"missing_contract_count": 0,
			"stale_contract_count": 0,
			"requires_runtime_apply": False,
		}
	contracts_reviewed = _optional_bool(contract_state.get("contracts_reviewed"), "contract_state.contracts_reviewed")
	missing_contract_count = _optional_int(contract_state.get("missing_contract_count")) or 0
	stale_contract_count = _optional_int(contract_state.get("stale_contract_count")) or 0
	return {
		"ready": contracts_reviewed and missing_contract_count == 0 and stale_contract_count == 0,
		"contracts_reviewed": contracts_reviewed,
		"missing_contract_count": missing_contract_count,
		"stale_contract_count": stale_contract_count,
		"requires_runtime_apply": False,
	}


def _build_next_actions(blockers: list[dict[str, Any]]) -> list[dict[str, str]]:
	if not blockers:
		return [
			{"action": "review_payroll_artifacts", "label": "Review payroll artifacts and statutory bases"},
			{"action": "request_human_approval", "label": "Request final human approval"},
		]
	actions = []
	for code in [blocker["code"] for blocker in blockers]:
		if code == "attendance_not_ready":
			actions.append({"action": "resolve_attendance_blockers", "label": "Resolve attendance blockers"})
		elif code == "approver_missing":
			actions.append({"action": "assign_payroll_approver", "label": "Assign payroll approver"})
		elif code == "payroll_entry_missing":
			actions.append({"action": "prepare_payroll_entry", "label": "Prepare Payroll Entry artifacts"})
		elif code == "statutory_artifacts_missing":
			actions.append({"action": "prepare_statutory_artifacts", "label": "Prepare statutory payroll artifacts"})
		elif code == "payslip_artifacts_missing":
			actions.append({"action": "prepare_payslip_artifacts", "label": "Prepare payslip artifacts"})
		elif code == "kakao_queue_not_ready":
			actions.append({"action": "prepare_kakao_queue", "label": "Prepare Kakao notification queue"})
		elif code == "expense_settlement_not_ready":
			actions.append({"action": "resolve_expense_settlements", "label": "Resolve expense settlements"})
		elif code == "employment_contracts_not_ready":
			actions.append({"action": "review_employment_contracts", "label": "Review employment contract artifacts"})
	return actions


def _build_review_checklist() -> list[dict[str, Any]]:
	return [
		_review_checklist_item(
			key="attendance_reviewed",
			label="Attendance exceptions reviewed",
			source_card="attendance",
		),
		_review_checklist_item(
			key="statutory_bases_reviewed",
			label="Statutory payroll bases and totals reviewed",
			source_card="payroll_artifacts",
		),
		_review_checklist_item(
			key="expense_settlements_reviewed",
			label="Expense settlements reviewed",
			source_card="expense_settlements",
		),
		_review_checklist_item(
			key="employment_contracts_reviewed",
			label="Employment contract artifacts reviewed",
			source_card="employment_contracts",
		),
		_review_checklist_item(
			key="payslip_kakao_artifacts_reviewed",
			label="Payslip artifacts and Kakao queue reviewed",
			source_card="notifications",
		),
		_review_checklist_item(
			key="human_approver_assigned",
			label="Human approver assigned for final authority",
			source_card="approval",
		),
	]


def _review_checklist_item(*, key: str, label: str, source_card: str) -> dict[str, Any]:
	return {
		"key": key,
		"label": label,
		"source_card": source_card,
		"checked": False,
		"requires_human_review": True,
		"ai_role": AI_ROLE,
	}


def _build_readiness_cards(
	*,
	attendance_state: dict[str, Any],
	payroll_artifacts: dict[str, Any],
	approval_state: dict[str, Any],
	notification_state: dict[str, Any],
	expense_state: dict[str, Any],
	contract_state: dict[str, Any],
) -> list[dict[str, Any]]:
	return [
		{
			"key": "attendance",
			"label": "Attendance readiness",
			"state": "ready" if attendance_state["ready"] else "blocked",
			"summary": {"unmarked_days": deepcopy(attendance_state["unmarked_days"])},
		},
		{
			"key": "payroll_artifacts",
			"label": "Payroll artifacts",
			"state": "ready" if payroll_artifacts["payroll_entry"] and payroll_artifacts["statutory_totals"] else "blocked",
			"summary": {"salary_slip_count": payroll_artifacts["salary_slip_count"]},
		},
		{
			"key": "approval",
			"label": "Human approval",
			"state": "ready" if approval_state["approver"] else "blocked",
			"summary": {"approver": approval_state["approver"], "status": approval_state["status"]},
		},
		{
			"key": "notifications",
			"label": "Payslip/Kakao readiness",
			"state": "ready" if notification_state["payslip_artifacts_ready"] and notification_state["kakao_queue_ready"] else "blocked",
			"summary": {
				"payslip_artifacts_ready": notification_state["payslip_artifacts_ready"],
				"kakao_queue_ready": notification_state["kakao_queue_ready"],
			},
		},
		{
			"key": "expense_settlements",
			"label": "Expense settlement readiness",
			"state": "ready" if expense_state["settlement_ready"] else "blocked",
			"summary": {
				"open_claim_count": expense_state["open_claim_count"],
				"approved_unpaid_count": expense_state["approved_unpaid_count"],
			},
		},
		{
			"key": "employment_contracts",
			"label": "Employment contract readiness",
			"state": "ready" if contract_state["ready"] else "blocked",
			"summary": {
				"missing_contract_count": contract_state["missing_contract_count"],
				"stale_contract_count": contract_state["stale_contract_count"],
			},
		},
	]


def _validate_optional_scope(source: dict[str, Any], *, company: str, workplace: str, label: str) -> None:
	source_company = str(source.get("company") or "").strip()
	if source_company and source_company != company:
		raise ValueError(f"{label}.company must match session company")
	source_workplace = str(source.get("workplace") or "").strip()
	if source_workplace and source_workplace != workplace:
		raise ValueError(f"{label}.workplace must match session workplace")


def _validate_optional_period(source: dict[str, Any], *, period_start: str, period_end: str, label: str) -> None:
	start = source.get("period_start", source.get("start_date"))
	end = source.get("period_end", source.get("end_date"))
	if start is not None and _parse_iso_date(start, f"{label}.period_start").isoformat() != period_start:
		raise ValueError(f"{label}.period_start must match session period_start")
	if end is not None and _parse_iso_date(end, f"{label}.period_end").isoformat() != period_end:
		raise ValueError(f"{label}.period_end must match session period_end")


def _require_explicit_scope(source: dict[str, Any], *, label: str) -> None:
	if not str(source.get("company") or "").strip():
		raise ValueError(f"{label}.company is required")
	if not str(source.get("workplace") or "").strip():
		raise ValueError(f"{label}.workplace is required")


def _require_explicit_period(source: dict[str, Any], *, label: str) -> None:
	if source.get("period_start", source.get("start_date")) is None:
		raise ValueError(f"{label}.period_start is required")
	if source.get("period_end", source.get("end_date")) is None:
		raise ValueError(f"{label}.period_end is required")


def _parse_iso_date(value: str | dt.date, fieldname: str) -> dt.date:
	if type(value) is dt.date:
		return value
	if isinstance(value, str):
		text = value.strip()
		if "T" in text:
			raise ValueError(f"{fieldname} must be an ISO date")
		try:
			return dt.date.fromisoformat(text)
		except ValueError as exc:
			raise ValueError(f"{fieldname} must be an ISO date") from exc
	raise ValueError(f"{fieldname} must be an ISO date")


def _require_text(value: Any, fieldname: str) -> str:
	text = str(value or "").strip()
	if not text:
		raise ValueError(f"{fieldname} is required")
	return text


def _require_string_text(value: Any, fieldname: str) -> str:
	if not isinstance(value, str):
		raise ValueError(f"{fieldname} must be a string")
	text = value.strip()
	if not text:
		raise ValueError(f"{fieldname} is required")
	return text


def _optional_payload(value: dict[str, Any] | None, fieldname: str) -> dict[str, Any]:
	if value is None:
		return {}
	if not isinstance(value, dict):
		raise ValueError(f"{fieldname} must be a dict")
	_reject_forbidden_score_fields(value, fieldname)
	return value


_FORBIDDEN_SCORE_KEYS = {"risk_score", "score", "probability", "success_rate", "legal_risk_score"}
_FORBIDDEN_SCORE_KEY_FRAGMENTS = ("risk_score", "probability", "success_rate")
_FORBIDDEN_NORMALIZED_SCORE_FRAGMENTS = ("riskscore", "probability", "successrate")


def _reject_forbidden_score_fields(value: Any, path: str) -> None:
	if isinstance(value, dict):
		for key, child in value.items():
			key_text = str(key)
			normalized_key = key_text.strip().lower().replace(" ", "_").replace("-", "_")
			compact_key = re.sub(r"[^a-z0-9]", "", key_text.lower())
			child_path = f"{path}.{key_text}"
			if (
				normalized_key in _FORBIDDEN_SCORE_KEYS
				or any(fragment in normalized_key for fragment in _FORBIDDEN_SCORE_KEY_FRAGMENTS)
				or any(fragment in compact_key for fragment in _FORBIDDEN_NORMALIZED_SCORE_FRAGMENTS)
			):
				raise ValueError(f"{path} must not include numeric score fields")
			_reject_forbidden_score_fields(child, child_path)
	elif isinstance(value, list):
		for index, child in enumerate(value):
			_reject_forbidden_score_fields(child, f"{path}[{index}]")


def _optional_note(value: Any) -> str | None:
	if value is None:
		return None
	if not isinstance(value, str):
		raise ValueError("note must be a string")
	text = value.strip()
	if not text:
		raise ValueError("note must not be blank")
	return text


def _optional_bool(value: Any, fieldname: str) -> bool:
	if value is None:
		return False
	if type(value) is not bool:
		raise ValueError(f"{fieldname} must be a boolean")
	return value


def _optional_int(value: Any) -> int | None:
	if value is None:
		return None
	if type(value) is not int:
		raise ValueError("count fields must be integers")
	if value < 0:
		raise ValueError("count fields must be non-negative")
	return value


__all__ = ["build_korea_payroll_closing_session", "build_korea_payroll_closing_audit_event"]
