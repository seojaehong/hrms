"""Frappe-facing read-only runtime API for Korea payroll closing worklists.

This endpoint queries persisted ``Korea Payroll Closing Draft`` rows and reuses the
framework-free payroll closing worklist contract for operator queue rendering. It
is strictly read-only: no save, submit, approve, send, provider call, or payroll
mutation is performed.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

try:  # pragma: no cover - exercised only inside a Frappe bench or test stub
	import frappe  # type: ignore
except ImportError:  # pragma: no cover - direct-run import without Frappe is unsupported for runtime reads
	frappe = None  # type: ignore

DOCTYPE = "Korea Payroll Closing Draft"
AI_ROLE = "assistant_only"
MUTATION_BOUNDARY = "draft_only_no_submit_no_approve_no_send"
SESSION_CONTRACT_TYPE = "korea_payroll_closing_session_v1"
DEFAULT_LIMIT = 50
MAX_LIMIT = 200
RUNTIME_READ_DOCTYPES = (DOCTYPE,)

ROW_FIELDS = [
	"name",
	"company",
	"workplace",
	"period_start",
	"period_end",
	"status",
	"source_payroll_entry",
	"source_session_contract_type",
	"mutation_boundary",
	"requires_human_approval",
	"ai_role",
	"payload",
	"audit_preview",
	"docstatus",
]

FORBIDDEN_SCORE_FRAGMENTS = (
	"score",
	"risk",
	"riskscore",
	"legalriskscore",
	"probability",
	"probabilityscore",
	"successrate",
	"closingsuccessrate",
)


def _whitelist(fn):
	if frappe is None:
		return fn
	return frappe.whitelist()(fn)


@_whitelist
def list_korea_payroll_closing_worklist_runtime(
	*,
	company: Any = None,
	workplaces: Any | None = None,
	limit: Any = DEFAULT_LIMIT,
) -> dict[str, Any]:
	"""Return a scoped operator worklist from persisted payroll closing drafts.

	company 미지정 시 Global Defaults default_company로 폴백한다
	(PWA가 ?company= 딥링크 없이 진입하는 기본 동선 지원).
	"""

	_runtime_required()
	if company is None:
		company = frappe.db.get_single_value("Global Defaults", "default_company")  # type: ignore[union-attr]
	company_text = _require_text(company, "company")
	workplace_payloads = None if workplaces is None else deepcopy(_coerce_list(workplaces, "workplaces"))
	limit_value = _coerce_limit(limit)
	_require_runtime_read_access()
	filters: dict[str, Any] = {"company": company_text, "docstatus": 0, "status": "draft_pending_human_approval"}
	if workplace_payloads is not None:
		filters["workplace"] = ("in", workplace_payloads)
	rows = frappe.get_list(  # type: ignore[union-attr]
		DOCTYPE,
		filters=filters,
		fields=ROW_FIELDS,
		order_by="period_end desc, modified desc",
		limit_page_length=limit_value,
	)
	runtime_sessions = [_runtime_session_from_draft_row(row) for row in rows]
	_seen_session_names: set[str] = set()
	for item in runtime_sessions:
		session_name = item["session"]["name"]
		if session_name in _seen_session_names:
			raise ValueError("payload.session.name values must be unique in payroll closing worklist runtime rows")
		_seen_session_names.add(session_name)
	core = _load_sibling_module("payroll_closing_worklist.py", "korea_payroll_closing_worklist_runtime_core")
	result = deepcopy(
		core.build_korea_payroll_closing_worklist(
			sessions=[item["session"] for item in runtime_sessions],
			company=company_text,
			workplaces=workplace_payloads,
		)
	)
	worklist_contract_type = result.get("contract_type")
	_session_extras = {item["session"]["name"]: item for item in runtime_sessions}
	for item in result.get("items", []):
		extra = _session_extras[item["name"]]
		session = extra["session"]
		item.update(
			{
				"runtime_action": "runtime_read_only",
				"requires_runtime_apply": False,
				"runtime_source_doctype": DOCTYPE,
				"draft_name": extra["draft_name"],
				"draft_status": extra["draft_status"],
				# 지정 결재자 read-only 노출 — "결재함 0건" 혼란 방지 UX
				# (마감 draft는 approval_state.approver 한 명에게만 배정된다)
				"approver": _approver_from_session(session),
				"employee_count": _employee_count_from_session(session),
				"readiness_cards": _safe_readiness_cards(session.get("readiness_cards", [])),
				"audit_preview": _safe_audit_preview(session.get("audit_preview", {})),
				"source_session": _source_session_metadata(session),
			}
		)
	result.update(
		{
			"contract_type": "korea_payroll_closing_worklist_runtime_api_v1",
			"worklist_contract_type": worklist_contract_type,
			"runtime_action": "runtime_read_only",
			"requires_runtime_apply": False,
			"requires_human_approval": True,
			"ai_role": AI_ROLE,
		}
	)
	_reject_forbidden_score_keys(result)
	return result


def _runtime_required() -> None:
	if frappe is None:
		raise RuntimeError("Frappe runtime is required for payroll closing worklist runtime reads")
	if not hasattr(frappe, "get_list"):
		raise RuntimeError("Frappe get_list API is required for payroll closing worklist runtime reads")
	if not hasattr(frappe, "only_for") or not hasattr(frappe, "has_permission"):
		raise RuntimeError("Frappe role and permission APIs are required for payroll closing worklist runtime reads")


def _require_runtime_read_access() -> None:
	frappe.only_for(["HR Manager"])  # type: ignore[union-attr]
	for doctype in RUNTIME_READ_DOCTYPES:
		if not frappe.has_permission(doctype, ptype="read"):  # type: ignore[union-attr]
			raise PermissionError(f"read permission is required for {doctype}")


def _runtime_session_from_draft_row(value: Any) -> dict[str, Any]:
	if not isinstance(value, dict):
		value = {field: getattr(value, field, None) for field in ROW_FIELDS}
	row = deepcopy(value)
	if row.get("source_session_contract_type") != SESSION_CONTRACT_TYPE:
		raise ValueError("source_session_contract_type must be korea_payroll_closing_session_v1")
	if row.get("mutation_boundary") != MUTATION_BOUNDARY:
		raise ValueError("mutation_boundary must remain draft_only_no_submit_no_approve_no_send")
	if _coerce_stored_bool(row.get("requires_human_approval"), "requires_human_approval") is not True:
		raise ValueError("requires_human_approval must be stored as true")
	if row.get("ai_role") != AI_ROLE:
		raise ValueError("ai_role must be assistant_only")
	payload = _coerce_json_object(row.get("payload"), "payload")
	if row.get("audit_preview") is not None:
		_validate_row_audit_preview(_coerce_json_object(row.get("audit_preview"), "audit_preview"))
	session = payload.get("session")
	if not isinstance(session, dict):
		raise ValueError("payload.session must be a JSON object")
	session = deepcopy(session)
	_reject_forbidden_score_keys(session)
	company = _require_text(row.get("company"), "company")
	workplace = _require_text(row.get("workplace"), "workplace")
	period_start = _normalize_iso_date(row.get("period_start"), "period_start")
	period_end = _normalize_iso_date(row.get("period_end"), "period_end")
	for fieldname, expected in (
		("contract_type", SESSION_CONTRACT_TYPE),
		("company", company),
		("workplace", workplace),
		("period_start", period_start),
		("period_end", period_end),
		("requires_human_approval", True),
		("ai_role", AI_ROLE),
	):
		if fieldname in {"requires_human_approval", "ai_role"} and fieldname not in session:
			session[fieldname] = expected
		elif session.get(fieldname) != expected:
			raise ValueError(f"payload.session.{fieldname} must match the stored draft")
	if "blockers" not in session:
		session["blockers"] = []
	if "next_actions" not in session:
		session["next_actions"] = []
	if "audit_preview" not in session:
		session["audit_preview"] = {"runtime_action": "preview_only", "requires_runtime_apply": False, "blocker_codes": []}
	if session.get("status") == "draft" and row.get("status") == "draft_pending_human_approval":
		blockers = session.get("blockers", [])
		session["status"] = "blocked" if isinstance(blockers, list) and blockers else "review_ready"
	name = session.get("name") or row.get("name")
	session["name"] = _require_text(name, "payload.session.name")
	if not isinstance(session.get("readiness_cards", []), list):
		raise ValueError("payload.session.readiness_cards must be a list when provided")
	if "audit_preview" in session and not isinstance(session["audit_preview"], dict):
		raise ValueError("payload.session.audit_preview must be a JSON object when provided")
	return {
		"draft_name": _require_text(row.get("name"), "name"),
		"draft_status": _require_text(row.get("status"), "status"),
		"session": session,
	}


def _approver_from_session(session: dict[str, Any]) -> str | None:
	"""세션 payload의 approval_state.approver를 read-only로 추출 (없으면 None)."""
	approval_state = session.get("approval_state")
	if not isinstance(approval_state, dict):
		return None
	approver = approval_state.get("approver")
	if not isinstance(approver, str) or not approver.strip():
		return None
	return approver.strip()


def _employee_count_from_session(session: dict[str, Any]) -> int | None:
	artifacts = session.get("payroll_artifacts")
	if not isinstance(artifacts, dict):
		return None
	value = artifacts.get("salary_slip_count") if "salary_slip_count" in artifacts else artifacts.get("employee_count")
	if value is None:
		return None
	if type(value) is not int or value < 0:
		raise ValueError("payload.session.payroll_artifacts salary count must be a non-negative integer")
	return value


def _source_session_metadata(session: dict[str, Any]) -> dict[str, Any]:
	return {
		"contract_type": session["contract_type"],
		"name": session["name"],
	}


def _safe_readiness_cards(value: Any) -> list[dict[str, Any]]:
	if not isinstance(value, list):
		raise ValueError("payload.session.readiness_cards must be a list when provided")
	cards: list[dict[str, Any]] = []
	for card in value:
		if not isinstance(card, dict):
			raise ValueError("payload.session.readiness_cards must contain JSON objects")
		cards.append(
			{
				"key": _require_text(card.get("key"), "payload.session.readiness_cards.key"),
				"label": _require_text(card.get("label"), "payload.session.readiness_cards.label"),
				"state": _require_text(card.get("state"), "payload.session.readiness_cards.state"),
				"summary": _require_text(card.get("summary"), "payload.session.readiness_cards.summary"),
			}
		)
	return cards


def _safe_audit_preview(value: Any) -> dict[str, Any]:
	if not isinstance(value, dict):
		raise ValueError("payload.session.audit_preview must be a JSON object when provided")
	blocker_codes = value.get("blocker_codes", [])
	if not isinstance(blocker_codes, list) or not all(isinstance(code, str) for code in blocker_codes):
		raise ValueError("payload.session.audit_preview.blocker_codes must be a list of strings")
	runtime_action = _require_text(value.get("runtime_action"), "payload.session.audit_preview.runtime_action")
	requires_runtime_apply = _require_bool(value.get("requires_runtime_apply"), "payload.session.audit_preview.requires_runtime_apply")
	if runtime_action != "preview_only" or requires_runtime_apply is not False:
		raise ValueError("payload.session.audit_preview must remain preview-only read metadata")
	return {
		"runtime_action": runtime_action,
		"requires_runtime_apply": False,
		"blocker_codes": [code for code in blocker_codes],
	}


def _validate_row_audit_preview(value: dict[str, Any]) -> None:
	_reject_forbidden_score_keys(value)
	runtime_action = _require_text(value.get("runtime_action"), "audit_preview.runtime_action")
	requires_runtime_apply = _require_bool(value.get("requires_runtime_apply"), "audit_preview.requires_runtime_apply")
	if runtime_action != "preview_only" or requires_runtime_apply is not False:
		raise ValueError("payload.session.audit_preview must remain preview-only read metadata")


def _require_bool(value: Any, fieldname: str) -> bool:
	if type(value) is not bool:
		raise ValueError(f"{fieldname} must be a boolean")
	return value


def _coerce_stored_bool(value: Any, fieldname: str) -> bool:
	if value is True or value == 1:
		return True
	if value is False or value == 0:
		return False
	raise ValueError(f"{fieldname} must be stored as a boolean check value")


def _normalize_iso_date(value: Any, fieldname: str) -> str:
	if type(value) is dt.date:
		return value.isoformat()
	if isinstance(value, str):
		try:
			return dt.date.fromisoformat(value.strip()).isoformat()
		except ValueError as exc:
			raise ValueError(f"{fieldname} must be an ISO date") from exc
	raise ValueError(f"{fieldname} must be an ISO date")


def _coerce_json_object(value: Any, fieldname: str) -> dict[str, Any]:
	coerced = _coerce_json_if_needed(value)
	if not isinstance(coerced, dict):
		raise ValueError(f"{fieldname} must be a JSON object")
	return coerced


def _coerce_list(value: Any, fieldname: str) -> list[str]:
	coerced = _coerce_json_if_needed(value)
	if not isinstance(coerced, list):
		raise ValueError(f"{fieldname} must be a list or JSON array")
	for item in coerced:
		if not isinstance(item, str) or not item.strip():
			raise ValueError(f"{fieldname} must contain non-empty strings")
	return [item.strip() for item in coerced]


def _coerce_json_if_needed(value: Any) -> Any:
	if isinstance(value, str):
		text = value.strip()
		if text.startswith("{") or text.startswith("["):
			try:
				return json.loads(text)
			except json.JSONDecodeError as exc:
				raise ValueError("JSON payload is invalid") from exc
	return value


def _coerce_limit(value: Any) -> int:
	if value is None:
		return DEFAULT_LIMIT
	if type(value) is int:
		limit = value
	elif isinstance(value, str) and value.strip().isdigit():
		limit = int(value.strip())
	else:
		raise ValueError("limit must be an integer")
	if limit < 1 or limit > MAX_LIMIT:
		raise ValueError(f"limit must be between 1 and {MAX_LIMIT}")
	return limit


def _require_text(value: Any, fieldname: str) -> str:
	if not isinstance(value, str) or not value.strip():
		raise ValueError(f"{fieldname} must be a non-empty string")
	return value.strip()


def _reject_forbidden_score_keys(value: Any) -> None:
	for key in _iter_json_keys(value):
		normalized_key = re.sub(r"[^a-z0-9]+", "_", key.strip().lower()).strip("_").replace("_", "")
		if any(fragment in normalized_key for fragment in FORBIDDEN_SCORE_FRAGMENTS):
			raise ValueError("score keys are not allowed in payroll closing worklist runtime payloads")


def _iter_json_keys(value: Any):
	if isinstance(value, dict):
		for key, nested in value.items():
			if isinstance(key, str):
				yield key
			yield from _iter_json_keys(nested)
	elif isinstance(value, list):
		for item in value:
			yield from _iter_json_keys(item)


def _load_sibling_module(filename: str, module_name: str):
	path = Path(__file__).with_name(filename)
	spec = importlib.util.spec_from_file_location(module_name, path)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


__all__ = ["list_korea_payroll_closing_worklist_runtime"]
