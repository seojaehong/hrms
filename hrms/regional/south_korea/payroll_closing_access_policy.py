"""Framework-free access policy for Korea payroll closing sessions.

This module is a preview-only permission/readiness contract for the payroll
closing session product spine. It does not mutate, approve, save, submit, send,
or call providers; later Frappe adapters can use the decision payload before
showing review/draft/audit actions.
"""

from __future__ import annotations

from typing import Any

SESSION_CONTRACT_TYPE = "korea_payroll_closing_session_v1"
ACCESS_DECISION_CONTRACT_TYPE = "korea_payroll_closing_access_decision_v1"
AI_ROLE = "assistant_only"

_ALLOWED_ACTIONS = {"review_session", "record_human_review", "request_approval"}
_ROLE_ALLOWED_ACTIONS = {
	"hq_hr_admin": ("review_session", "record_human_review", "request_approval"),
	"branch_manager": ("review_session", "record_human_review", "request_approval"),
	"external_labor_advisor": ("review_session",),
	"employee": (),
}
_WORKPLACE_SCOPED_ROLES = {"branch_manager", "external_labor_advisor", "employee"}


def build_payroll_closing_access_decision(
	session: dict[str, Any],
	*,
	actor: dict[str, Any],
	action: str,
) -> dict[str, Any]:
	"""Build a side-effect-free access decision for a closing session action."""

	if not isinstance(session, dict):
		raise ValueError("session must be a dict")
	if session.get("contract_type") != SESSION_CONTRACT_TYPE:
		raise ValueError(f"session.contract_type must be {SESSION_CONTRACT_TYPE}")

	company = _require_text(session.get("company"), "session.company")
	workplace = _require_text(session.get("workplace"), "session.workplace")
	period_start = _require_text(session.get("period_start"), "session.period_start")
	period_end = _require_text(session.get("period_end"), "session.period_end")
	status = _require_text(session.get("status"), "session.status")
	if session.get("requires_human_approval") is not True:
		raise ValueError("session.requires_human_approval must be true")
	if session.get("ai_role") != AI_ROLE:
		raise ValueError(f"session.ai_role must be {AI_ROLE}")

	if not isinstance(actor, dict):
		raise ValueError("actor must be a dict")
	actor_user = _require_text(actor.get("user"), "actor.user")
	role = _require_text(actor.get("role"), "actor.role")
	if role not in _ROLE_ALLOWED_ACTIONS:
		allowed = ", ".join(sorted(_ROLE_ALLOWED_ACTIONS))
		raise ValueError(f"actor.role must be one of: {allowed}")
	actor_company = _require_text(actor.get("company"), "actor.company")
	if actor_company != company:
		raise ValueError("actor.company must match session company")

	action_text = _require_text(action, "action")
	if action_text not in _ALLOWED_ACTIONS:
		allowed = ", ".join(sorted(_ALLOWED_ACTIONS))
		raise ValueError(f"action must be one of: {allowed}")

	allowed_actions = list(_ROLE_ALLOWED_ACTIONS[role])
	workplaces: list[str] | None = None
	if role in _WORKPLACE_SCOPED_ROLES:
		workplaces = _normalize_workplaces(actor.get("workplaces"), "actor.workplaces")

	reason = "allowed"
	decision = "allow"

	if not allowed_actions:
		decision = "deny"
		reason = "role_not_allowed"
	elif role in _WORKPLACE_SCOPED_ROLES:
		if workplace not in workplaces:
			decision = "deny"
			reason = "workplace_scope_mismatch"
		elif action_text not in allowed_actions:
			decision = "deny"
			reason = "action_not_allowed"
	elif action_text not in allowed_actions:
		decision = "deny"
		reason = "action_not_allowed"

	session_ref = _optional_text(session.get("name"), "session.name")

	return {
		"contract_type": ACCESS_DECISION_CONTRACT_TYPE,
		"source_session_contract_type": SESSION_CONTRACT_TYPE,
		"actor": actor_user,
		"role": role,
		"requested_action": action_text,
		"decision": decision,
		"reason": reason,
		"allowed_actions": allowed_actions if decision == "allow" or reason == "action_not_allowed" else [],
		"scope": {
			"company": company,
			"workplace": workplace,
			"period_start": period_start,
			"period_end": period_end,
			"session_status": status,
		},
		"session_ref": session_ref,
		"runtime_action": "preview_only",
		"requires_runtime_apply": False,
		"requires_human_approval": True,
		"ai_role": AI_ROLE,
	}


def _normalize_workplaces(value: Any, fieldname: str) -> list[str]:
	if not isinstance(value, list):
		raise ValueError(f"{fieldname} must be a list")
	workplaces: list[str] = []
	for item in value:
		workplaces.append(_require_text(item, f"{fieldname}[]"))
	return workplaces


def _optional_text(value: Any, fieldname: str) -> str | None:
	if value is None:
		return None
	return _require_text(value, fieldname)


def _require_text(value: Any, fieldname: str) -> str:
	if not isinstance(value, str):
		raise ValueError(f"{fieldname} must be a string")
	text = value.strip()
	if not text:
		raise ValueError(f"{fieldname} is required")
	return text


__all__ = ["build_payroll_closing_access_decision"]
