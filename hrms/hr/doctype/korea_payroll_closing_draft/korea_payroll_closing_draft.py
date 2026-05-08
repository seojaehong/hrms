# Copyright (c) 2026, Frappe HRMS contributors
# For license information, please see license.txt

from __future__ import annotations

import datetime as dt
import json
import re
from copy import deepcopy
from typing import Any

import frappe
from frappe.model.document import Document


EXPECTED_STATUS = "draft_pending_human_approval"
ALLOWED_HUMAN_REVIEW_STATUSES = {
	"draft_pending_human_approval",
	"draft_human_approved",
	"draft_human_rejected",
	"draft_changes_requested",
}
REVIEW_ACTION_CONTRACT_TYPE = "korea_payroll_closing_draft_review_action_v1"
REVIEW_ACTION_MUTATION_BOUNDARY = "human_review_only_no_submit_no_send_no_provider_call"
REVIEW_RUNTIME_MUTATION_BOUNDARY = "human_review_status_only_no_submit_no_send_no_provider_call"
EXPECTED_SESSION_CONTRACT_TYPE = "korea_payroll_closing_session_v1"
EXPECTED_MUTATION_BOUNDARY = "draft_only_no_submit_no_approve_no_send"
EXPECTED_AI_ROLE = "assistant_only"
FORBIDDEN_SCORE_FRAGMENTS = (
	"score",
	"riskscore",
	"legalriskscore",
	"probability",
	"probabilityscore",
	"successrate",
	"closingsuccessrate",
)


class KoreaPayrollClosingDraft(Document):
	"""Runtime draft record boundary for Korea payroll closing.

	This DocType persists only a human-review draft payload. It intentionally does
	not submit, approve, send notifications, call providers, or perform payroll
	mutation. Those actions require later guarded runtime adapters.
	"""

	def validate(self):
		self._normalize_scope_text()
		self._validate_period_order()
		self._validate_safety_boundary()
		self._validate_no_duplicate_open_draft()
		payload = _parse_json_object(self.payload, "Payload")
		audit_preview = _parse_json_object(self.audit_preview, "Audit Preview")
		_reject_forbidden_score_keys(payload, "Payload")
		_reject_forbidden_score_keys(audit_preview, "Audit Preview")
		self._validate_embedded_scope(payload.get("session"), "Payload session")
		self._validate_embedded_scope(audit_preview, "Audit preview")
		self.payload = json.dumps(payload, ensure_ascii=False, sort_keys=True)
		self.audit_preview = json.dumps(audit_preview, ensure_ascii=False, sort_keys=True)

	def _normalize_scope_text(self):
		for fieldname, label in (("company", "Company"), ("workplace", "Workplace")):
			value = (getattr(self, fieldname, None) or "").strip()
			if not value:
				frappe.throw(frappe._(f"{label} is required."))
			setattr(self, fieldname, value)

	def _validate_period_order(self):
		period_start = _parse_iso_date(getattr(self, "period_start", None), "Period start")
		period_end = _parse_iso_date(getattr(self, "period_end", None), "Period end")
		if period_start > period_end:
			frappe.throw(frappe._("Period start must be on or before period end."))

	def _validate_embedded_scope(self, value, label: str):
		if not isinstance(value, dict):
			frappe.throw(frappe._(f"{label} must be a JSON object."))
		for fieldname, expected in (
			("company", self.company),
			("workplace", self.workplace),
			("period_start", str(self.period_start)),
			("period_end", str(self.period_end)),
		):
			if fieldname not in value:
				frappe.throw(frappe._(f"{label} {fieldname} is required."))
			if value.get(fieldname) != expected:
				frappe.throw(frappe._(f"{label} {fieldname} must match the draft {fieldname}."))

	def _validate_safety_boundary(self):
		if getattr(self, "status", None) not in ALLOWED_HUMAN_REVIEW_STATUSES:
			frappe.throw(frappe._("Korea Payroll Closing Draft status must stay within guarded human-review states."))
		if getattr(self, "source_session_contract_type", None) != EXPECTED_SESSION_CONTRACT_TYPE:
			frappe.throw(frappe._("Source session contract type must be korea_payroll_closing_session_v1."))
		if getattr(self, "mutation_boundary", None) != EXPECTED_MUTATION_BOUNDARY:
			frappe.throw(frappe._("Mutation boundary must remain draft_only_no_submit_no_approve_no_send."))
		if getattr(self, "ai_role", None) != EXPECTED_AI_ROLE:
			frappe.throw(frappe._("AI role must be assistant_only."))
		if getattr(self, "requires_human_approval", None) not in (1, True):
			frappe.throw(frappe._("Human approval is required for Korea payroll closing drafts."))

	def _validate_no_duplicate_open_draft(self):
		_ensure_no_duplicate_open_draft(
			{
				"company": self.company,
				"workplace": self.workplace,
				"period_start": _parse_iso_date(getattr(self, "period_start", None), "Period start").isoformat(),
				"period_end": _parse_iso_date(getattr(self, "period_end", None), "Period end").isoformat(),
			},
			exclude_name=getattr(self, "name", None),
		)


def create_korea_payroll_closing_draft_from_apply_plan(apply_plan: dict[str, Any], *, actor: str) -> dict[str, Any]:
	"""Persist a reviewed Korea payroll closing draft from a validated apply plan.

	This is the first controlled runtime persistence boundary. It creates only a
	draft DocType row; it does not submit, approve, send Kakao notifications, call
	providers, or create payroll documents.
	"""

	actor_text = _require_string_text(actor, "actor")
	fields = _validated_apply_plan_fields(apply_plan, actor=actor_text)
	_ensure_no_duplicate_open_draft(fields)
	created = frappe.get_doc(fields).insert()
	return {
		"contract_type": "korea_payroll_closing_draft_runtime_insert_v1",
		"source_apply_plan_contract_type": "korea_payroll_closing_draft_apply_plan_v1",
		"runtime_action": "runtime_draft_created",
		"requires_runtime_apply": False,
		"mutation_boundary": EXPECTED_MUTATION_BOUNDARY,
		"doctype": "Korea Payroll Closing Draft",
		"name": getattr(created, "name", None),
		"status": EXPECTED_STATUS,
		"company": fields["company"],
		"workplace": fields["workplace"],
		"period_start": fields["period_start"],
		"period_end": fields["period_end"],
		"source_payroll_entry": fields["source_payroll_entry"],
		"approver": fields["approver"],
		"actor": actor_text,
		"docstatus": 0,
		"requires_human_approval": True,
		"ai_role": EXPECTED_AI_ROLE,
	}
def apply_korea_payroll_closing_draft_review_action(review_action: dict[str, Any], *, actor: str) -> dict[str, Any]:
	"""Apply a guarded human-review status update to a persisted draft row.

	This is intentionally narrower than payroll approval or submission: it updates
	the draft review status only, then saves the existing draft row. It does not
	submit, approve payroll, send notifications, call providers, or create payroll
	documents.
	"""

	actor_text = _require_string_text(actor, "actor")
	fields = _validated_review_action_fields(review_action, actor=actor_text)
	doc = frappe.get_doc("Korea Payroll Closing Draft", fields["name"])
	previous_status = getattr(doc, "status", None)
	_validate_review_target_doc(doc, fields)
	doc.status = fields["status"]
	saved = doc.save()
	return {
		"contract_type": "korea_payroll_closing_draft_review_runtime_apply_v1",
		"source_review_action_contract_type": REVIEW_ACTION_CONTRACT_TYPE,
		"runtime_action": "runtime_draft_review_status_updated",
		"requires_runtime_apply": False,
		"mutation_boundary": REVIEW_RUNTIME_MUTATION_BOUNDARY,
		"doctype": "Korea Payroll Closing Draft",
		"name": getattr(saved, "name", fields["name"]),
		"previous_status": previous_status,
		"status": fields["status"],
		"action": fields["action"],
		"actor": actor_text,
		"company": fields["company"],
		"workplace": fields["workplace"],
		"period_start": fields["period_start"],
		"period_end": fields["period_end"],
		"source_payroll_entry": fields["source_payroll_entry"],
		"requires_human_approval": True,
		"ai_role": EXPECTED_AI_ROLE,
	}


def _ensure_no_duplicate_open_draft(fields: dict[str, Any], *, exclude_name: str | None = None) -> None:
	db = getattr(frappe, "db", None)
	if db is None:
		return
	filters = {
		"company": fields["company"],
		"workplace": fields["workplace"],
		"period_start": fields["period_start"],
		"period_end": fields["period_end"],
		"docstatus": 0,
	}
	if exclude_name:
		filters["name"] = ["!=", exclude_name]
	existing = db.exists("Korea Payroll Closing Draft", filters)
	if existing:
		frappe.throw(frappe._("Korea Payroll Closing Draft already exists for this company/workplace/period."))


def _parse_json_object(value, label: str) -> dict:
	if not isinstance(value, str) or not value.strip():
		frappe.throw(frappe._(f"{label} must be valid JSON."))
	try:
		parsed = json.loads(value)
	except json.JSONDecodeError:
		frappe.throw(frappe._(f"{label} must be valid JSON."))
	if not isinstance(parsed, dict):
		frappe.throw(frappe._(f"{label} must be a JSON object."))
	return parsed


def _reject_forbidden_score_keys(value, label: str):
	for key in _iter_json_keys(value):
		normalized_key = _normalize_score_key(key)
		if any(fragment in normalized_key for fragment in FORBIDDEN_SCORE_FRAGMENTS):
			frappe.throw(frappe._(f"{label} must not contain numeric risk/probability/success-rate score fields."))


def _iter_json_keys(value):
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


def _validated_review_action_fields(review_action: dict[str, Any], *, actor: str) -> dict[str, Any]:
	if not isinstance(review_action, dict):
		frappe.throw(frappe._("review_action must be a JSON object."))
	_reject_forbidden_score_keys(review_action, "review_action")
	if review_action.get("contract_type") != REVIEW_ACTION_CONTRACT_TYPE:
		frappe.throw(frappe._("review_action.contract_type must be korea_payroll_closing_draft_review_action_v1."))
	if review_action.get("source_draft_contract_type") != "korea_payroll_closing_draft_runtime_insert_v1":
		frappe.throw(frappe._("review_action.source_draft_contract_type must be korea_payroll_closing_draft_runtime_insert_v1."))
	if review_action.get("runtime_action") != "preview_only":
		frappe.throw(frappe._("review_action.runtime_action must be preview_only."))
	if review_action.get("requires_runtime_apply") is not True:
		frappe.throw(frappe._("review_action.requires_runtime_apply must be true."))
	if review_action.get("mutation_boundary") != REVIEW_ACTION_MUTATION_BOUNDARY:
		frappe.throw(frappe._("review_action.mutation_boundary must be human_review_only_no_submit_no_send_no_provider_call."))
	if review_action.get("would_update_doctype") != "Korea Payroll Closing Draft":
		frappe.throw(frappe._("review_action.would_update_doctype must be Korea Payroll Closing Draft."))
	if review_action.get("requires_human_approval") is not True:
		frappe.throw(frappe._("review_action.requires_human_approval must be true."))
	if review_action.get("ai_role") != EXPECTED_AI_ROLE:
		frappe.throw(frappe._("review_action.ai_role must be assistant_only."))
	if _require_string_text(review_action.get("actor"), "review_action.actor") != actor:
		frappe.throw(frappe._("review_action.actor must match actor."))

	source_draft = review_action.get("source_draft")
	if not isinstance(source_draft, dict):
		frappe.throw(frappe._("review_action.source_draft must be a JSON object."))
	if source_draft.get("contract_type") != "korea_payroll_closing_draft_runtime_insert_v1":
		frappe.throw(frappe._("source_draft.contract_type must be korea_payroll_closing_draft_runtime_insert_v1."))
	if source_draft.get("runtime_action") != "runtime_draft_created":
		frappe.throw(frappe._("source_draft.runtime_action must be runtime_draft_created."))
	if source_draft.get("requires_runtime_apply") is not False:
		frappe.throw(frappe._("source_draft.requires_runtime_apply must be false."))
	if source_draft.get("mutation_boundary") != EXPECTED_MUTATION_BOUNDARY:
		frappe.throw(frappe._("source_draft.mutation_boundary must remain draft_only_no_submit_no_approve_no_send."))
	if source_draft.get("doctype") != "Korea Payroll Closing Draft":
		frappe.throw(frappe._("source_draft.doctype must be Korea Payroll Closing Draft."))
	if source_draft.get("status") != EXPECTED_STATUS:
		frappe.throw(frappe._("source_draft.status must be draft_pending_human_approval."))
	if source_draft.get("docstatus") != 0:
		frappe.throw(frappe._("source_draft.docstatus must be 0."))
	if source_draft.get("requires_human_approval") is not True:
		frappe.throw(frappe._("source_draft.requires_human_approval must be true."))
	if source_draft.get("ai_role") != EXPECTED_AI_ROLE:
		frappe.throw(frappe._("source_draft.ai_role must be assistant_only."))

	status = _require_string_text(review_action.get("would_set_status"), "review_action.would_set_status")
	if status not in (ALLOWED_HUMAN_REVIEW_STATUSES - {EXPECTED_STATUS}):
		frappe.throw(frappe._("review_action.would_set_status must be a guarded human-review result status."))
	fields = {
		"name": _require_string_text(review_action.get("would_update_name"), "review_action.would_update_name"),
		"status": status,
		"action": _require_string_text(review_action.get("action"), "review_action.action"),
		"company": _require_string_text(review_action.get("company"), "review_action.company"),
		"workplace": _require_string_text(review_action.get("workplace"), "review_action.workplace"),
		"period_start": _parse_iso_date(review_action.get("period_start"), "review_action.period_start").isoformat(),
		"period_end": _parse_iso_date(review_action.get("period_end"), "review_action.period_end").isoformat(),
		"source_payroll_entry": _require_string_text(review_action.get("source_payroll_entry"), "review_action.source_payroll_entry"),
		"audit_preview": deepcopy(review_action.get("audit_preview")),
	}
	if not isinstance(fields["audit_preview"], dict):
		frappe.throw(frappe._("review_action.audit_preview must be a JSON object."))
	for fieldname, fieldvalue in fields.items():
		if fieldname == "audit_preview":
			continue
		source_key = "name" if fieldname == "name" else fieldname
		if fieldname in {"status", "action"}:
			continue
		if source_draft.get(source_key) != fieldvalue:
			frappe.throw(frappe._(f"review_action.{fieldname} must match source_draft.{source_key}."))
	if review_action.get("would_set_status") != fields["audit_preview"].get("would_set_status"):
		frappe.throw(frappe._("review_action.would_set_status must match audit_preview.would_set_status."))
	return fields


def _validate_review_target_doc(doc: Any, fields: dict[str, Any]) -> None:
	checks = {
		"name": fields["name"],
		"company": fields["company"],
		"workplace": fields["workplace"],
		"period_start": fields["period_start"],
		"period_end": fields["period_end"],
		"source_payroll_entry": fields["source_payroll_entry"],
		"status": EXPECTED_STATUS,
		"docstatus": 0,
		"requires_human_approval": 1,
		"ai_role": EXPECTED_AI_ROLE,
		"mutation_boundary": EXPECTED_MUTATION_BOUNDARY,
	}
	for fieldname, expected in checks.items():
		actual = getattr(doc, fieldname, None)
		if fieldname == "requires_human_approval":
			if actual not in (1, True):
				frappe.throw(frappe._("target draft requires_human_approval must be true."))
		elif str(actual) != str(expected):
			frappe.throw(frappe._(f"target draft {fieldname} must match the review action."))


def _validated_apply_plan_fields(apply_plan: dict[str, Any], *, actor: str) -> dict[str, Any]:
	if not isinstance(apply_plan, dict):
		frappe.throw(frappe._("apply_plan must be a JSON object."))
	if apply_plan.get("contract_type") != "korea_payroll_closing_draft_apply_plan_v1":
		frappe.throw(frappe._("apply_plan.contract_type must be korea_payroll_closing_draft_apply_plan_v1."))
	if apply_plan.get("source_draft_contract_type") != "korea_payroll_closing_draft_v1":
		frappe.throw(frappe._("apply_plan.source_draft_contract_type must be korea_payroll_closing_draft_v1."))
	if apply_plan.get("runtime_action") != "preview_runtime_draft_apply":
		frappe.throw(frappe._("apply_plan.runtime_action must be preview_runtime_draft_apply."))
	if apply_plan.get("requires_runtime_apply") is not True:
		frappe.throw(frappe._("apply_plan.requires_runtime_apply must be true."))
	if apply_plan.get("requires_human_approval") is not True:
		frappe.throw(frappe._("apply_plan.requires_human_approval must be true."))
	if apply_plan.get("ai_role") != EXPECTED_AI_ROLE:
		frappe.throw(frappe._("apply_plan.ai_role must be assistant_only."))
	if apply_plan.get("mutation_boundary") != EXPECTED_MUTATION_BOUNDARY:
		frappe.throw(frappe._("mutation_boundary must remain draft_only_no_submit_no_approve_no_send."))
	if apply_plan.get("would_create_doctype") != "Korea Payroll Closing Draft":
		frappe.throw(frappe._("apply_plan.would_create_doctype must be Korea Payroll Closing Draft."))
	if apply_plan.get("docstatus") != 0:
		frappe.throw(frappe._("apply_plan.docstatus must be 0."))

	preview = apply_plan.get("doctype_insert_preview")
	if not isinstance(preview, dict):
		frappe.throw(frappe._("doctype_insert_preview must be a JSON object."))
	if preview.get("doctype") != "Korea Payroll Closing Draft":
		frappe.throw(frappe._("doctype_insert_preview.doctype must be Korea Payroll Closing Draft."))
	if preview.get("runtime_action") != "preview_only":
		frappe.throw(frappe._("doctype_insert_preview.runtime_action must be preview_only."))
	if preview.get("requires_runtime_apply") is not True:
		frappe.throw(frappe._("doctype_insert_preview.requires_runtime_apply must be true."))
	if preview.get("mutation_boundary") != EXPECTED_MUTATION_BOUNDARY:
		frappe.throw(frappe._("mutation_boundary must remain draft_only_no_submit_no_approve_no_send."))
	fields = preview.get("fields")
	if not isinstance(fields, dict):
		frappe.throw(frappe._("doctype_insert_preview.fields must be a JSON object."))

	allowed_fields = {
		"doctype",
		"docstatus",
		"company",
		"workplace",
		"period_start",
		"period_end",
		"status",
		"source_payroll_entry",
		"approver",
		"source_session_contract_type",
		"mutation_boundary",
		"requires_human_approval",
		"ai_role",
		"payload",
		"audit_preview",
	}
	for fieldname in fields:
		if fieldname not in allowed_fields:
			frappe.throw(frappe._(f"doctype_insert_preview.fields.{fieldname} is not allowed."))
	validated = deepcopy(fields)
	if validated.get("doctype") not in (None, "Korea Payroll Closing Draft"):
		frappe.throw(frappe._("doctype_insert_preview.fields.doctype must be Korea Payroll Closing Draft."))
	validated["doctype"] = "Korea Payroll Closing Draft"
	if validated.get("docstatus") != 0:
		frappe.throw(frappe._("doctype_insert_preview.fields.docstatus must be 0."))
	if validated.get("status") != EXPECTED_STATUS:
		frappe.throw(frappe._("Korea Payroll Closing Draft stays draft_pending_human_approval."))
	if validated.get("source_session_contract_type") != EXPECTED_SESSION_CONTRACT_TYPE:
		frappe.throw(frappe._("Source session contract type must be korea_payroll_closing_session_v1."))
	if validated.get("mutation_boundary") != EXPECTED_MUTATION_BOUNDARY:
		frappe.throw(frappe._("mutation_boundary must remain draft_only_no_submit_no_approve_no_send."))
	if validated.get("requires_human_approval") not in (1, True):
		frappe.throw(frappe._("Human approval is required for Korea payroll closing drafts."))
	if validated.get("ai_role") != EXPECTED_AI_ROLE:
		frappe.throw(frappe._("AI role must be assistant_only."))

	for fieldname in ("company", "workplace", "source_payroll_entry", "approver"):
		validated[fieldname] = _require_string_text(validated.get(fieldname), f"doctype_insert_preview.fields.{fieldname}")
	validated["period_start"] = _parse_iso_date(validated.get("period_start"), "Period start").isoformat()
	validated["period_end"] = _parse_iso_date(validated.get("period_end"), "Period end").isoformat()
	if dt.date.fromisoformat(validated["period_start"]) > dt.date.fromisoformat(validated["period_end"]):
		frappe.throw(frappe._("Period start must be on or before period end."))
	for fieldname in (
		"company",
		"workplace",
		"period_start",
		"period_end",
		"status",
		"source_payroll_entry",
		"approver",
		"docstatus",
		"requires_human_approval",
		"ai_role",
	):
		if apply_plan.get(fieldname) != validated[fieldname]:
			frappe.throw(
				frappe._(f"apply_plan.{fieldname} must match doctype_insert_preview.fields.{fieldname}.")
			)
	if _require_string_text(apply_plan.get("actor"), "apply_plan.actor") != actor:
		frappe.throw(frappe._("apply_plan.actor must match actor."))

	payload = _parse_json_object(validated.get("payload"), "Payload")
	audit_preview = _parse_json_object(validated.get("audit_preview"), "Audit Preview")
	_reject_forbidden_score_keys(payload, "Payload")
	_reject_forbidden_score_keys(audit_preview, "Audit Preview")
	_validate_scope_dict(payload.get("session"), "Payload session", validated)
	_validate_scope_dict(audit_preview, "Audit preview", validated)
	validated["payload"] = json.dumps(payload, ensure_ascii=False, sort_keys=True)
	validated["audit_preview"] = json.dumps(audit_preview, ensure_ascii=False, sort_keys=True)
	return validated


def _validate_scope_dict(value: Any, label: str, expected_fields: dict[str, Any]) -> None:
	if not isinstance(value, dict):
		frappe.throw(frappe._(f"{label} must be a JSON object."))
	for fieldname in ("company", "workplace", "period_start", "period_end"):
		if fieldname not in value:
			frappe.throw(frappe._(f"{label} {fieldname} is required."))
		if value.get(fieldname) != expected_fields[fieldname]:
			frappe.throw(frappe._(f"{label} {fieldname} must match the draft {fieldname}."))


def _require_string_text(value: Any, label: str) -> str:
	if not isinstance(value, str) or not value.strip():
		frappe.throw(frappe._(f"{label} must be a non-empty string."))
	return value.strip()


def _parse_iso_date(value, label: str) -> dt.date:
	try:
		return dt.date.fromisoformat(str(value))
	except (TypeError, ValueError):
		frappe.throw(frappe._(f"{label} must be an ISO date."))
