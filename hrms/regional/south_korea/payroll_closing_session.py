"""Framework-free Korea payroll closing session read model.

This module composes existing preview/helper outputs into one operator-facing
payroll-closing session snapshot. It intentionally avoids Frappe imports,
persistence, provider calls, and legal/probability scoring. Runtime adapters can
later persist or mutate from this read model behind human approval.
"""

from __future__ import annotations

import datetime as dt
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


def _optional_payload(value: dict[str, Any] | None, fieldname: str) -> dict[str, Any]:
	if value is None:
		return {}
	if not isinstance(value, dict):
		raise ValueError(f"{fieldname} must be a dict")
	return value


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


__all__ = ["build_korea_payroll_closing_session"]
