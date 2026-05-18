"""Framework-free Korea payroll closing draft review audit-log contract.

This module converts a guarded runtime draft-review status update into an audit
log creation preview. It remains side-effect-free: no save, submit, payroll
approval, notification send, provider call, or payroll document creation is
performed here.
"""

from __future__ import annotations

import datetime as dt
import re
from copy import deepcopy
from typing import Any

CONTRACT_TYPE = "korea_payroll_closing_draft_review_audit_log_v1"
RUNTIME_APPLY_CONTRACT_TYPES = {
	"korea_payroll_closing_draft_review_runtime_apply_v1",
	"korea_payroll_closing_draft_review_runtime_apply_api_v1",
}
CORE_RUNTIME_APPLY_CONTRACT_TYPE = "korea_payroll_closing_draft_review_runtime_apply_v1"
SOURCE_REVIEW_ACTION_CONTRACT_TYPE = "korea_payroll_closing_draft_review_action_v1"
EXPECTED_RUNTIME_ACTION = "runtime_draft_review_status_updated"
EXPECTED_REVIEW_MUTATION_BOUNDARY = "human_review_status_only_no_submit_no_send_no_provider_call"
AUDIT_LOG_MUTATION_BOUNDARY = "audit_log_only_no_submit_no_send_no_provider_call"
EXPECTED_AI_ROLE = "assistant_only"
EXPECTED_PREVIOUS_STATUS = "draft_pending_human_approval"

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


def build_korea_payroll_closing_draft_review_audit_log(
	runtime_apply: dict[str, Any],
	*,
	audit_actor: str,
) -> dict[str, Any]:
	"""Build an audit-log creation preview from a runtime review apply result."""

	if not isinstance(runtime_apply, dict):
		raise ValueError("runtime_apply must be a JSON object")
	_reject_forbidden_score_keys(runtime_apply, "runtime_apply")

	audit_actor_text = _require_text(audit_actor, "audit_actor")
	_validate_runtime_apply_contract(runtime_apply)

	action = _require_text(runtime_apply.get("action"), "runtime_apply.action")
	if action not in _ALLOWED_ACTION_STATUSES:
		raise ValueError("action must be one of approve_draft, reject_draft, request_changes")
	status = _require_text(runtime_apply.get("status"), "runtime_apply.status")
	if status != _ALLOWED_ACTION_STATUSES[action]:
		raise ValueError("status must be a guarded human-review result status matching action")
	previous_status = _require_text(runtime_apply.get("previous_status"), "runtime_apply.previous_status")
	if previous_status != EXPECTED_PREVIOUS_STATUS:
		raise ValueError("previous_status must be draft_pending_human_approval")

	period_start = _parse_iso_date(runtime_apply.get("period_start"), "runtime_apply.period_start")
	period_end = _parse_iso_date(runtime_apply.get("period_end"), "runtime_apply.period_end")
	if period_start > period_end:
		raise ValueError("period_start must be on or before period_end")

	company = _require_text(runtime_apply.get("company"), "runtime_apply.company")
	workplace = _require_text(runtime_apply.get("workplace"), "runtime_apply.workplace")
	draft_name = _require_text(runtime_apply.get("name"), "runtime_apply.name")
	source_payroll_entry = _require_text(runtime_apply.get("source_payroll_entry"), "runtime_apply.source_payroll_entry")
	review_actor = _require_text(runtime_apply.get("actor"), "runtime_apply.actor")
	period_start_text = period_start.isoformat()
	period_end_text = period_end.isoformat()
	source_contract_type = runtime_apply["contract_type"]
	runtime_apply_contract_type = runtime_apply.get("runtime_apply_contract_type") or source_contract_type

	audit_event = {
		"event_type": "korea_payroll_closing_draft_review_status_audit_v1",
		"runtime_action": "preview_only",
		"requires_runtime_apply": True,
		"mutation_boundary": AUDIT_LOG_MUTATION_BOUNDARY,
		"would_create_doctype": "Korea Payroll Closing Review Audit Log",
		"draft_name": draft_name,
		"previous_status": previous_status,
		"status": status,
		"action": action,
		"review_actor": review_actor,
		"audit_actor": audit_actor_text,
		"company": company,
		"workplace": workplace,
		"period_start": period_start_text,
		"period_end": period_end_text,
		"source_payroll_entry": source_payroll_entry,
		"requires_human_approval": True,
		"ai_role": EXPECTED_AI_ROLE,
	}
	return {
		"contract_type": CONTRACT_TYPE,
		"source_runtime_apply_contract_type": source_contract_type,
		"runtime_apply_contract_type": runtime_apply_contract_type,
		"source_review_action_contract_type": SOURCE_REVIEW_ACTION_CONTRACT_TYPE,
		"runtime_action": "preview_only",
		"requires_runtime_apply": True,
		"would_create_doctype": "Korea Payroll Closing Review Audit Log",
		"mutation_boundary": AUDIT_LOG_MUTATION_BOUNDARY,
		"draft_name": draft_name,
		"previous_status": previous_status,
		"status": status,
		"action": action,
		"review_actor": review_actor,
		"audit_actor": audit_actor_text,
		"company": company,
		"workplace": workplace,
		"period_start": period_start_text,
		"period_end": period_end_text,
		"source_payroll_entry": source_payroll_entry,
		"audit_event": audit_event,
		"source_runtime_apply": deepcopy(runtime_apply),
		"requires_human_approval": True,
		"ai_role": EXPECTED_AI_ROLE,
	}


def _validate_runtime_apply_contract(runtime_apply: dict[str, Any]) -> None:
	contract_type = runtime_apply.get("contract_type")
	if contract_type not in RUNTIME_APPLY_CONTRACT_TYPES:
		raise ValueError(
			"runtime_apply.contract_type must be korea_payroll_closing_draft_review_runtime_apply_v1 "
			"or korea_payroll_closing_draft_review_runtime_apply_api_v1"
		)
	runtime_apply_contract_type = runtime_apply.get("runtime_apply_contract_type")
	if contract_type.endswith("_api_v1") or runtime_apply_contract_type is not None:
		if runtime_apply_contract_type != CORE_RUNTIME_APPLY_CONTRACT_TYPE:
			raise ValueError("runtime_apply.runtime_apply_contract_type must be korea_payroll_closing_draft_review_runtime_apply_v1")
	if runtime_apply.get("source_review_action_contract_type") != SOURCE_REVIEW_ACTION_CONTRACT_TYPE:
		raise ValueError("runtime_apply.source_review_action_contract_type must be korea_payroll_closing_draft_review_action_v1")
	if runtime_apply.get("runtime_action") != EXPECTED_RUNTIME_ACTION:
		raise ValueError("runtime_apply.runtime_action must be runtime_draft_review_status_updated")
	if runtime_apply.get("requires_runtime_apply") is not False:
		raise ValueError("runtime_apply.requires_runtime_apply must be false")
	if runtime_apply.get("mutation_boundary") != EXPECTED_REVIEW_MUTATION_BOUNDARY:
		raise ValueError("runtime_apply.mutation_boundary must remain human_review_status_only_no_submit_no_send_no_provider_call")
	if runtime_apply.get("doctype") != "Korea Payroll Closing Draft":
		raise ValueError("runtime_apply.doctype must be Korea Payroll Closing Draft")
	if runtime_apply.get("requires_human_approval") is not True:
		raise ValueError("requires_human_approval must be true")
	if runtime_apply.get("ai_role") != EXPECTED_AI_ROLE:
		raise ValueError("runtime_apply.ai_role must be assistant_only")


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


def _reject_forbidden_score_keys(value: Any, label: str) -> None:
	for key in _iter_json_keys(value):
		normalized = _normalize_score_key(key)
		if any(fragment in normalized for fragment in _FORBIDDEN_SCORE_FRAGMENTS):
			raise ValueError(f"{key} is not allowed in {label}")


def _iter_json_keys(value: Any):
	if isinstance(value, dict):
		for key, nested in value.items():
			if isinstance(key, str):
				yield key
			yield from _iter_json_keys(nested)
	elif isinstance(value, list):
		for item in value:
			yield from _iter_json_keys(item)


def _normalize_score_key(key: str) -> str:
	return re.sub(r"[^a-z0-9]+", "_", key.strip().lower()).strip("_").replace("_", "")


__all__ = ["build_korea_payroll_closing_draft_review_audit_log"]
