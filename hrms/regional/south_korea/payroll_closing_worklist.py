"""Framework-free Korea payroll closing operator worklist.

This module turns already-built payroll closing sessions into a route-only
operator queue for Admin Home / closing-center navigation. It intentionally
avoids Frappe imports, persistence, provider calls, approval, sending, and
legal/probability scoring.
"""

from __future__ import annotations

import datetime as dt
from copy import deepcopy
from typing import Any
from urllib.parse import quote

SESSION_CONTRACT_TYPE = "korea_payroll_closing_session_v1"
WORKLIST_CONTRACT_TYPE = "korea_payroll_closing_worklist_v1"
AI_ROLE = "assistant_only"
_ALLOWED_STATUS = {"blocked", "review_ready"}


def build_korea_payroll_closing_worklist(
	*,
	sessions: list[dict[str, Any]],
	company: str,
	workplaces: list[str] | None = None,
) -> dict[str, Any]:
	"""Build a side-effect-free operator worklist from closing sessions.

	The worklist is a navigation/readiness contract, not a mutation boundary. It
	fails closed on malformed sessions and cross-company data; workplace scope is
	applied as an allowlist so branch operators do not see other locations.
	"""

	company_text = _require_text(company, "company")
	if not isinstance(sessions, list):
		raise ValueError("sessions must be a list")
	workplace_scope = _normalize_workplaces(workplaces)

	items: list[dict[str, Any]] = []
	for raw_session in sessions:
		session = _normalize_session(raw_session, company=company_text)
		if workplace_scope is not None and session["workplace"] not in workplace_scope:
			continue
		items.append(_build_item(session))

	items.sort(key=_sort_key)
	blocked_count = sum(1 for item in items if item["status"] == "blocked")
	review_ready_count = sum(1 for item in items if item["status"] == "review_ready")
	return {
		"contract_type": WORKLIST_CONTRACT_TYPE,
		"company": company_text,
		"workplaces": deepcopy(workplace_scope) if workplace_scope is not None else sorted({item["workplace"] for item in items}),
		"summary": {
			"total_count": len(items),
			"blocked_count": blocked_count,
			"review_ready_count": review_ready_count,
		},
		"items": items,
		"runtime_action": "preview_only",
		"requires_runtime_apply": False,
		"requires_human_approval": True,
		"ai_role": AI_ROLE,
	}


def _normalize_session(value: Any, *, company: str) -> dict[str, Any]:
	if not isinstance(value, dict):
		raise ValueError("session must be a dict")
	session = deepcopy(value)
	if session.get("contract_type") != SESSION_CONTRACT_TYPE:
		raise ValueError(f"session.contract_type must be {SESSION_CONTRACT_TYPE}")
	if session.get("requires_human_approval") is not True:
		raise ValueError("session.requires_human_approval must be true")
	if session.get("ai_role") != AI_ROLE:
		raise ValueError(f"session.ai_role must be {AI_ROLE}")
	if session.get("company") != company:
		raise ValueError("session.company must match worklist company")
	workplace = _require_text(session.get("workplace"), "session.workplace")
	status = _require_text(session.get("status"), "session.status")
	if status not in _ALLOWED_STATUS:
		raise ValueError("session.status must be blocked or review_ready")
	period_start = _parse_iso_date(session.get("period_start"), "session.period_start")
	period_end = _parse_iso_date(session.get("period_end"), "session.period_end")
	if period_start > period_end:
		raise ValueError("session.period_start must be on or before session.period_end")
	blockers = session.get("blockers")
	if not isinstance(blockers, list):
		raise ValueError("session.blockers must be a list")
	next_actions = session.get("next_actions")
	if not isinstance(next_actions, list):
		raise ValueError("session.next_actions must be a list")
	return session | {
		"workplace": workplace,
		"status": status,
		"period_start": period_start.isoformat(),
		"period_end": period_end.isoformat(),
	}


def _build_item(session: dict[str, Any]) -> dict[str, Any]:
	name = session.get("name") or _default_session_name(session)
	name_text = _require_text(name, "session.name")
	blocker_codes = [_normalize_blocker_code(blocker) for blocker in session["blockers"]]
	return {
		"name": name_text,
		"company": session["company"],
		"workplace": session["workplace"],
		"period_start": session["period_start"],
		"period_end": session["period_end"],
		"status": session["status"],
		"blocker_codes": blocker_codes,
		"primary_action": _primary_action(session),
		"route": f"korea-payroll-closing-session/{quote(name_text, safe='')}",
		"payroll_entry": deepcopy(session.get("payroll_artifacts", {})).get("payroll_entry"),
		"requires_human_approval": True,
		"ai_role": AI_ROLE,
	}


def _primary_action(session: dict[str, Any]) -> dict[str, Any]:
	for action in session["next_actions"]:
		if not isinstance(action, dict):
			raise ValueError("session.next_actions items must be dicts")
		name = _require_text(action.get("action"), "next_action.action")
		label = action.get("label")
		if label is not None:
			label = _require_text(label, "next_action.label")
		return {
			"action": name,
			"label": label or name.replace("_", " ").title(),
			"requires_runtime_apply": False,
		}
	if session["status"] == "blocked":
		return {"action": "review_blockers", "label": "Review blockers", "requires_runtime_apply": False}
	return {"action": "review_payroll_artifacts", "label": "Review payroll artifacts", "requires_runtime_apply": False}


def _normalize_blocker_code(blocker: Any) -> str:
	if not isinstance(blocker, dict):
		raise ValueError("session.blockers items must be dicts")
	return _require_text(blocker.get("code"), "blocker.code")


def _normalize_workplaces(workplaces: list[str] | None) -> list[str] | None:
	if workplaces is None:
		return None
	if not isinstance(workplaces, list):
		raise ValueError("workplaces must be a list of strings")
	normalized = []
	for workplace in workplaces:
		if not isinstance(workplace, str) or not workplace.strip():
			raise ValueError("workplaces must be a list of strings")
		normalized.append(workplace.strip())
	return normalized


def _require_text(value: Any, fieldname: str) -> str:
	if not isinstance(value, str) or not value.strip():
		raise ValueError(f"{fieldname} is required")
	return value.strip()


def _parse_iso_date(value: Any, fieldname: str) -> dt.date:
	if isinstance(value, str):
		try:
			return dt.date.fromisoformat(value)
		except ValueError as exc:
			raise ValueError(f"{fieldname} must be an ISO date") from exc
	if type(value) is dt.date:
		return value
	raise ValueError(f"{fieldname} must be an ISO date")


def _default_session_name(session: dict[str, Any]) -> str:
	period = session["period_end"][:7]
	workplace = session["workplace"].replace(" ", "-").upper()
	return f"KPCS-{period}-{workplace}"


def _sort_key(item: dict[str, Any]) -> tuple[int, str, str]:
	status_rank = 0 if item["status"] == "blocked" else 1
	return status_rank, item["period_end"], item["workplace"]


__all__ = ["build_korea_payroll_closing_worklist"]
