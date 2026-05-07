"""Framework-free Korea payroll closing draft human-review action contract.

This module bridges a persisted runtime draft row into the next guarded
human-review boundary. It remains side-effect-free: no save, submit, approve,
notification send, payroll document creation, or provider call is performed.
"""

from __future__ import annotations

import datetime as dt
import re
from copy import deepcopy
from typing import Any

CONTRACT_TYPE = "korea_payroll_closing_draft_review_action_v1"
SOURCE_DRAFT_CONTRACT_TYPE = "korea_payroll_closing_draft_runtime_insert_v1"
EXPECTED_RUNTIME_ACTION = "runtime_draft_created"
EXPECTED_STATUS = "draft_pending_human_approval"
EXPECTED_AI_ROLE = "assistant_only"
EXPECTED_DRAFT_MUTATION_BOUNDARY = "draft_only_no_submit_no_approve_no_send"
REVIEW_MUTATION_BOUNDARY = "human_review_only_no_submit_no_send_no_provider_call"

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


def build_korea_payroll_closing_draft_review_action(
	draft: dict[str, Any],
	*,
	actor: str,
	action: str,
	note: str | None = None,
) -> dict[str, Any]:
	"""Build a preview-only human-review action for a payroll closing draft.

	The returned payload is suitable for a later runtime workflow adapter to apply
	after permission checks. This helper validates the runtime draft contract,
	assigned approver, action allowlist, period scope, human approval, and
	assistant-only AI boundary before copying any source data.
	"""

	if not isinstance(draft, dict):
		raise ValueError("draft must be a JSON object")
	_reject_forbidden_score_keys(draft, "payroll closing draft review payloads")

	actor_text = _require_text(actor, "actor")
	action_text = _require_text(action, "action")
	if action_text not in _ALLOWED_ACTION_STATUSES:
		raise ValueError(f"action must be one of {', '.join(sorted(_ALLOWED_ACTION_STATUSES))}")

	note_text = "" if note is None else _require_optional_text(note, "note")
	if action_text in {"reject_draft", "request_changes"} and not note_text:
		raise ValueError("note is required for reject_draft/request_changes")

	_validate_draft_contract(draft)
	approver = _require_text(draft.get("approver"), "draft.approver")
	if actor_text != approver:
		raise ValueError("actor must match draft.approver")

	period_start = _parse_iso_date(draft.get("period_start"), "draft.period_start")
	period_end = _parse_iso_date(draft.get("period_end"), "draft.period_end")
	if period_start > period_end:
		raise ValueError("draft.period_start must be on or before draft.period_end")

	company = _require_text(draft.get("company"), "draft.company")
	workplace = _require_text(draft.get("workplace"), "draft.workplace")
	would_update_name = _require_text(draft.get("name"), "draft.name")
	source_payroll_entry = _require_text(draft.get("source_payroll_entry"), "draft.source_payroll_entry")
	would_set_status = _ALLOWED_ACTION_STATUSES[action_text]
	period_start_text = period_start.isoformat()
	period_end_text = period_end.isoformat()

	audit_preview = {
		"event_type": "korea_payroll_closing_draft_human_review_v1",
		"runtime_action": "preview_only",
		"requires_runtime_apply": True,
		"mutation_boundary": REVIEW_MUTATION_BOUNDARY,
		"company": company,
		"workplace": workplace,
		"period_start": period_start_text,
		"period_end": period_end_text,
		"draft_name": would_update_name,
		"source_payroll_entry": source_payroll_entry,
		"previous_status": EXPECTED_STATUS,
		"would_set_status": would_set_status,
		"action": action_text,
		"actor": actor_text,
		"note": note_text,
		"requires_human_approval": True,
		"ai_role": EXPECTED_AI_ROLE,
	}
	return {
		"contract_type": CONTRACT_TYPE,
		"source_draft_contract_type": SOURCE_DRAFT_CONTRACT_TYPE,
		"runtime_action": "preview_only",
		"requires_runtime_apply": True,
		"mutation_boundary": REVIEW_MUTATION_BOUNDARY,
		"would_update_doctype": "Korea Payroll Closing Draft",
		"would_update_name": would_update_name,
		"would_set_status": would_set_status,
		"action": action_text,
		"actor": actor_text,
		"note": note_text,
		"company": company,
		"workplace": workplace,
		"period_start": period_start_text,
		"period_end": period_end_text,
		"source_payroll_entry": source_payroll_entry,
		"source_draft": deepcopy(draft),
		"audit_preview": audit_preview,
		"requires_human_approval": True,
		"ai_role": EXPECTED_AI_ROLE,
	}


def _validate_draft_contract(draft: dict[str, Any]) -> None:
	if draft.get("contract_type") != SOURCE_DRAFT_CONTRACT_TYPE:
		raise ValueError("draft.contract_type must be korea_payroll_closing_draft_runtime_insert_v1")
	if draft.get("runtime_action") != EXPECTED_RUNTIME_ACTION:
		raise ValueError("draft.runtime_action must be runtime_draft_created")
	if draft.get("requires_runtime_apply") is not False:
		raise ValueError("draft.requires_runtime_apply must be false")
	if draft.get("mutation_boundary") != EXPECTED_DRAFT_MUTATION_BOUNDARY:
		raise ValueError("draft.mutation_boundary must remain draft_only_no_submit_no_approve_no_send")
	if draft.get("doctype") != "Korea Payroll Closing Draft":
		raise ValueError("draft.doctype must be Korea Payroll Closing Draft")
	if draft.get("status") != EXPECTED_STATUS:
		raise ValueError("draft.status must be draft_pending_human_approval")
	if draft.get("docstatus") != 0:
		raise ValueError("draft.docstatus must be 0")
	if draft.get("requires_human_approval") is not True:
		raise ValueError("draft.requires_human_approval must be true")
	if draft.get("ai_role") != EXPECTED_AI_ROLE:
		raise ValueError("draft.ai_role must be assistant_only")


def _require_text(value: Any, label: str) -> str:
	if not isinstance(value, str) or not value.strip():
		raise ValueError(f"{label} must be a non-empty string")
	return value.strip()


def _require_optional_text(value: Any, label: str) -> str:
	if not isinstance(value, str):
		raise ValueError(f"{label} must be a string")
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


__all__ = ["build_korea_payroll_closing_draft_review_action"]
