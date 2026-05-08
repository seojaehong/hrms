# Copyright (c) 2026, Frappe HRMS contributors
# For license information, please see license.txt

from __future__ import annotations

import datetime as dt
import json
import re
from typing import Any

import frappe
from frappe.model.document import Document


AUDIT_LOG_CONTRACT_TYPE = "korea_payroll_closing_draft_review_audit_log_v1"
RUNTIME_INSERT_CONTRACT_TYPE = "korea_payroll_closing_review_audit_log_runtime_insert_v1"
EXPECTED_RUNTIME_ACTION = "preview_only"
RUNTIME_INSERT_ACTION = "runtime_review_audit_log_created"
EXPECTED_MUTATION_BOUNDARY = "audit_log_only_no_submit_no_send_no_provider_call"
EXPECTED_AI_ROLE = "assistant_only"
EXPECTED_PREVIOUS_STATUS = "draft_pending_human_approval"
ALLOWED_ACTION_STATUSES = {
	"approve_draft": "draft_human_approved",
	"reject_draft": "draft_human_rejected",
	"request_changes": "draft_changes_requested",
}
FORBIDDEN_SCORE_FRAGMENTS = (
	"score",
	"riskscore",
	"legalriskscore",
	"probability",
	"probabilityscore",
	"successrate",
	"closingsuccessrate",
)


class KoreaPayrollClosingReviewAuditLog(Document):
	"""Runtime audit row for guarded Korea payroll closing draft review actions.

	This DocType persists only the review audit event. It does not submit payroll,
	approve payroll, send notifications, call providers, or create payroll docs.
	"""

	def validate(self):
		self._normalize_scope_text()
		self._validate_period_order()
		self._validate_safety_boundary()
		audit_event = _parse_json_object(self.audit_event, "Audit event")
		source_runtime_apply = _parse_json_object(self.source_runtime_apply, "Source runtime apply")
		_reject_forbidden_score_keys(audit_event, "audit_event")
		_reject_forbidden_score_keys(source_runtime_apply, "source_runtime_apply")
		self._validate_embedded_scope(audit_event, "Audit event")
		self._validate_embedded_scope(source_runtime_apply, "Source runtime apply", draft_field="name")
		_validate_audit_event_safety(audit_event, _doc_fields(self), label="audit_event")
		_validate_source_runtime_apply_safety(source_runtime_apply, _doc_fields(self), label="source_runtime_apply")
		self.audit_event = json.dumps(audit_event, ensure_ascii=False, sort_keys=True)
		self.source_runtime_apply = json.dumps(source_runtime_apply, ensure_ascii=False, sort_keys=True)

	def _normalize_scope_text(self):
		for fieldname, label in (
			("company", "Company"),
			("workplace", "Workplace"),
			("draft_name", "Payroll closing draft"),
			("source_payroll_entry", "Source payroll entry"),
			("previous_status", "Previous status"),
			("status", "Status"),
			("action", "Review action"),
			("review_actor", "Review actor"),
			("audit_actor", "Audit actor"),
		):
			value = (getattr(self, fieldname, None) or "").strip()
			if not value:
				frappe.throw(frappe._(f"{label} is required."))
			setattr(self, fieldname, value)

	def _validate_period_order(self):
		period_start = _parse_iso_date(getattr(self, "period_start", None), "Period start")
		period_end = _parse_iso_date(getattr(self, "period_end", None), "Period end")
		if period_start > period_end:
			frappe.throw(frappe._("Period start must be on or before period end."))

	def _validate_safety_boundary(self):
		if getattr(self, "action", None) not in ALLOWED_ACTION_STATUSES:
			frappe.throw(frappe._("action must be one of approve_draft, reject_draft, request_changes."))
		if getattr(self, "status", None) != ALLOWED_ACTION_STATUSES[getattr(self, "action")]:
			frappe.throw(frappe._("status must stay within guarded human-review audit states."))
		if getattr(self, "previous_status", None) != EXPECTED_PREVIOUS_STATUS:
			frappe.throw(frappe._("Previous status must be draft_pending_human_approval."))
		if getattr(self, "source_audit_log_contract_type", None) != AUDIT_LOG_CONTRACT_TYPE:
			frappe.throw(frappe._("Source audit log contract type must be korea_payroll_closing_draft_review_audit_log_v1."))
		if getattr(self, "mutation_boundary", None) != EXPECTED_MUTATION_BOUNDARY:
			frappe.throw(frappe._("Mutation boundary must remain audit_log_only_no_submit_no_send_no_provider_call."))
		if getattr(self, "requires_human_approval", None) not in (1, True):
			frappe.throw(frappe._("Human approval is required for Korea payroll closing review audit logs."))
		if getattr(self, "ai_role", None) != EXPECTED_AI_ROLE:
			frappe.throw(frappe._("AI role must be assistant_only."))

	def _validate_embedded_scope(self, value: dict[str, Any], label: str, *, draft_field: str = "draft_name"):
		for fieldname, expected in (
			("company", self.company),
			("workplace", self.workplace),
			("period_start", str(self.period_start)),
			("period_end", str(self.period_end)),
			(draft_field, self.draft_name),
			("status", self.status),
			("action", self.action),
		):
			if fieldname not in value:
				frappe.throw(frappe._(f"{label} {fieldname} is required."))
			if value.get(fieldname) != expected:
				public_fieldname = "draft_name" if draft_field == "name" and fieldname == "name" else fieldname
				frappe.throw(frappe._(f"{label} {public_fieldname} must match the audit log {public_fieldname}."))


def create_korea_payroll_closing_review_audit_log(audit_log: dict[str, Any], *, audit_actor: str) -> dict[str, Any]:
	"""Persist a guarded payroll closing draft-review audit log row.

	The adapter accepts only the core audit-log preview contract and creates only a
	DocType row with ``docstatus = 0``. It does not submit, approve, send, call
	providers, or create payroll documents.
	"""

	audit_actor_text = _require_string_text(audit_actor, "audit_actor")
	fields = _validated_audit_log_fields(audit_log, audit_actor=audit_actor_text)
	created = frappe.get_doc(fields).insert()
	return {
		"contract_type": RUNTIME_INSERT_CONTRACT_TYPE,
		"source_audit_log_contract_type": AUDIT_LOG_CONTRACT_TYPE,
		"runtime_action": RUNTIME_INSERT_ACTION,
		"requires_runtime_apply": False,
		"mutation_boundary": EXPECTED_MUTATION_BOUNDARY,
		"doctype": "Korea Payroll Closing Review Audit Log",
		"name": getattr(created, "name", None),
		"draft_name": fields["draft_name"],
		"previous_status": fields["previous_status"],
		"status": fields["status"],
		"action": fields["action"],
		"review_actor": fields["review_actor"],
		"audit_actor": fields["audit_actor"],
		"company": fields["company"],
		"workplace": fields["workplace"],
		"period_start": fields["period_start"],
		"period_end": fields["period_end"],
		"source_payroll_entry": fields["source_payroll_entry"],
		"docstatus": 0,
		"requires_human_approval": True,
		"ai_role": EXPECTED_AI_ROLE,
	}


def _validated_audit_log_fields(audit_log: dict[str, Any], *, audit_actor: str) -> dict[str, Any]:
	if not isinstance(audit_log, dict):
		frappe.throw(frappe._("audit_log must be a JSON object."))
	if audit_log.get("contract_type") != AUDIT_LOG_CONTRACT_TYPE:
		frappe.throw(frappe._("audit_log.contract_type must be korea_payroll_closing_draft_review_audit_log_v1."))
	if audit_log.get("runtime_action") != EXPECTED_RUNTIME_ACTION:
		frappe.throw(frappe._("audit_log.runtime_action must be preview_only."))
	if audit_log.get("requires_runtime_apply") is not True:
		frappe.throw(frappe._("audit_log.requires_runtime_apply must be true."))
	if audit_log.get("would_create_doctype") != "Korea Payroll Closing Review Audit Log":
		frappe.throw(frappe._("audit_log.would_create_doctype must be Korea Payroll Closing Review Audit Log."))
	if audit_log.get("mutation_boundary") != EXPECTED_MUTATION_BOUNDARY:
		frappe.throw(frappe._("audit_log.mutation_boundary must remain audit_log_only_no_submit_no_send_no_provider_call."))
	if audit_log.get("requires_human_approval") is not True:
		frappe.throw(frappe._("audit_log.requires_human_approval must be true."))
	if audit_log.get("ai_role") != EXPECTED_AI_ROLE:
		frappe.throw(frappe._("audit_log.ai_role must be assistant_only."))
	if _require_string_text(audit_log.get("audit_actor"), "audit_log.audit_actor") != audit_actor:
		frappe.throw(frappe._("audit_log.audit_actor must match audit_actor."))

	fields = {
		"doctype": "Korea Payroll Closing Review Audit Log",
		"docstatus": 0,
		"company": _require_string_text(audit_log.get("company"), "audit_log.company"),
		"workplace": _require_string_text(audit_log.get("workplace"), "audit_log.workplace"),
		"period_start": _parse_iso_date(audit_log.get("period_start"), "audit_log.period_start").isoformat(),
		"period_end": _parse_iso_date(audit_log.get("period_end"), "audit_log.period_end").isoformat(),
		"draft_name": _require_string_text(audit_log.get("draft_name"), "audit_log.draft_name"),
		"source_payroll_entry": _require_string_text(audit_log.get("source_payroll_entry"), "audit_log.source_payroll_entry"),
		"previous_status": _require_string_text(audit_log.get("previous_status"), "audit_log.previous_status"),
		"status": _require_string_text(audit_log.get("status"), "audit_log.status"),
		"action": _require_string_text(audit_log.get("action"), "audit_log.action"),
		"review_actor": _require_string_text(audit_log.get("review_actor"), "audit_log.review_actor"),
		"audit_actor": audit_actor,
		"source_audit_log_contract_type": AUDIT_LOG_CONTRACT_TYPE,
		"mutation_boundary": EXPECTED_MUTATION_BOUNDARY,
		"requires_human_approval": 1,
		"ai_role": EXPECTED_AI_ROLE,
	}
	if fields["period_start"] > fields["period_end"]:
		frappe.throw(frappe._("audit_log.period_start must be on or before audit_log.period_end."))
	if fields["action"] not in ALLOWED_ACTION_STATUSES:
		frappe.throw(frappe._("audit_log.action must be one of approve_draft, reject_draft, request_changes."))
	if fields["status"] != ALLOWED_ACTION_STATUSES[fields["action"]]:
		frappe.throw(frappe._("audit_log.status must match action."))
	if fields["previous_status"] != EXPECTED_PREVIOUS_STATUS:
		frappe.throw(frappe._("audit_log.previous_status must be draft_pending_human_approval."))

	audit_event = _require_json_object_value(audit_log.get("audit_event"), "audit_event")
	source_runtime_apply = _require_json_object_value(audit_log.get("source_runtime_apply"), "source_runtime_apply")
	_reject_forbidden_score_keys(audit_event, "audit_event")
	_reject_forbidden_score_keys(source_runtime_apply, "source_runtime_apply")
	_validate_payload_scope(audit_event, fields, "audit_event", draft_field="draft_name")
	_validate_payload_scope(source_runtime_apply, fields, "source_runtime_apply", draft_field="name")
	_validate_audit_event_safety(audit_event, fields, label="audit_event")
	_validate_source_runtime_apply_safety(source_runtime_apply, fields, label="source_runtime_apply")
	fields["audit_event"] = json.dumps(audit_event, ensure_ascii=False, sort_keys=True)
	fields["source_runtime_apply"] = json.dumps(source_runtime_apply, ensure_ascii=False, sort_keys=True)
	return fields


def _validate_payload_scope(payload: dict[str, Any], fields: dict[str, Any], label: str, *, draft_field: str) -> None:
	for fieldname, expected in (
		("company", fields["company"]),
		("workplace", fields["workplace"]),
		("period_start", fields["period_start"]),
		("period_end", fields["period_end"]),
		(draft_field, fields["draft_name"]),
		("status", fields["status"]),
		("action", fields["action"]),
	):
		if payload.get(fieldname) != expected:
			public_fieldname = "draft_name" if draft_field == "name" and fieldname == "name" else fieldname
			frappe.throw(frappe._(f"{label}.{public_fieldname} must match audit_log.{public_fieldname}."))


def _validate_audit_event_safety(payload: dict[str, Any], fields: dict[str, Any], *, label: str) -> None:
	_expected_values = {
		"event_type": "korea_payroll_closing_draft_review_status_audit_v1",
		"runtime_action": "preview_only",
		"requires_runtime_apply": True,
		"mutation_boundary": EXPECTED_MUTATION_BOUNDARY,
		"would_create_doctype": "Korea Payroll Closing Review Audit Log",
		"previous_status": fields["previous_status"],
		"source_payroll_entry": fields["source_payroll_entry"],
		"review_actor": fields["review_actor"],
		"audit_actor": fields["audit_actor"],
		"requires_human_approval": True,
		"ai_role": EXPECTED_AI_ROLE,
	}
	_validate_exact_payload_values(payload, _expected_values, label=label)


def _validate_source_runtime_apply_safety(payload: dict[str, Any], fields: dict[str, Any], *, label: str) -> None:
	contract_type = payload.get("contract_type")
	if contract_type not in {
		"korea_payroll_closing_draft_review_runtime_apply_v1",
		"korea_payroll_closing_draft_review_runtime_apply_api_v1",
	}:
		frappe.throw(frappe._(f"{label}.contract_type must be korea_payroll_closing_draft_review_runtime_apply_v1 or korea_payroll_closing_draft_review_runtime_apply_api_v1."))
	runtime_apply_contract_type = payload.get("runtime_apply_contract_type")
	if contract_type.endswith("_api_v1") or runtime_apply_contract_type is not None:
		if runtime_apply_contract_type != "korea_payroll_closing_draft_review_runtime_apply_v1":
			frappe.throw(frappe._(f"{label}.runtime_apply_contract_type must be korea_payroll_closing_draft_review_runtime_apply_v1."))
	_expected_values = {
		"source_review_action_contract_type": "korea_payroll_closing_draft_review_action_v1",
		"runtime_action": "runtime_draft_review_status_updated",
		"requires_runtime_apply": False,
		"doctype": "Korea Payroll Closing Draft",
		"previous_status": fields["previous_status"],
		"source_payroll_entry": fields["source_payroll_entry"],
		"actor": fields["review_actor"],
		"requires_human_approval": True,
		"ai_role": EXPECTED_AI_ROLE,
	}
	_validate_exact_payload_values(payload, _expected_values, label=label)
	if payload.get("mutation_boundary") != "human_review_status_only_no_submit_no_send_no_provider_call":
		frappe.throw(frappe._(f"{label}.mutation_boundary must remain human_review_status_only_no_submit_no_send_no_provider_call."))


def _validate_exact_payload_values(payload: dict[str, Any], expected_values: dict[str, Any], *, label: str) -> None:
	for fieldname, expected in expected_values.items():
		if payload.get(fieldname) != expected:
			if isinstance(expected, bool):
				expected_text = str(expected).lower()
			else:
				expected_text = str(expected)
			frappe.throw(frappe._(f"{label}.{fieldname} must be {expected_text}."))


def _doc_fields(doc: KoreaPayrollClosingReviewAuditLog) -> dict[str, Any]:
	return {
		"company": doc.company,
		"workplace": doc.workplace,
		"period_start": str(doc.period_start),
		"period_end": str(doc.period_end),
		"draft_name": doc.draft_name,
		"source_payroll_entry": doc.source_payroll_entry,
		"previous_status": doc.previous_status,
		"status": doc.status,
		"action": doc.action,
		"review_actor": doc.review_actor,
		"audit_actor": doc.audit_actor,
	}


def _parse_json_object(value, label: str) -> dict[str, Any]:
	if not isinstance(value, str) or not value.strip():
		frappe.throw(frappe._(f"{label} must be valid JSON."))
	try:
		parsed = json.loads(value)
	except json.JSONDecodeError:
		frappe.throw(frappe._(f"{label} must be valid JSON."))
	if not isinstance(parsed, dict):
		frappe.throw(frappe._(f"{label} must be a JSON object."))
	return parsed


def _require_json_object_value(value: Any, label: str) -> dict[str, Any]:
	if not isinstance(value, dict):
		frappe.throw(frappe._(f"{label} must be a JSON object."))
	return value


def _require_string_text(value: Any, label: str) -> str:
	if not isinstance(value, str) or not value.strip():
		frappe.throw(frappe._(f"{label} must be a non-empty string."))
	return value.strip()


def _parse_iso_date(value: Any, label: str) -> dt.date:
	if not isinstance(value, str):
		frappe.throw(frappe._(f"{label} must be an ISO date."))
	try:
		return dt.date.fromisoformat(value)
	except ValueError:
		frappe.throw(frappe._(f"{label} must be an ISO date."))


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
