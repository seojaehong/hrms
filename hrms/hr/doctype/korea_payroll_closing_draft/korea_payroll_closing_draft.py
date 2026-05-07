# Copyright (c) 2026, Frappe HRMS contributors
# For license information, please see license.txt

from __future__ import annotations

import datetime as dt
import json
import re

import frappe
from frappe.model.document import Document


EXPECTED_STATUS = "draft_pending_human_approval"
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
		if getattr(self, "status", None) != EXPECTED_STATUS:
			frappe.throw(frappe._("Korea Payroll Closing Draft stays draft_pending_human_approval."))
		if getattr(self, "source_session_contract_type", None) != EXPECTED_SESSION_CONTRACT_TYPE:
			frappe.throw(frappe._("Source session contract type must be korea_payroll_closing_session_v1."))
		if getattr(self, "mutation_boundary", None) != EXPECTED_MUTATION_BOUNDARY:
			frappe.throw(frappe._("Mutation boundary must remain draft_only_no_submit_no_approve_no_send."))
		if getattr(self, "ai_role", None) != EXPECTED_AI_ROLE:
			frappe.throw(frappe._("AI role must be assistant_only."))
		if getattr(self, "requires_human_approval", None) not in (1, True):
			frappe.throw(frappe._("Human approval is required for Korea payroll closing drafts."))


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


def _parse_iso_date(value, label: str) -> dt.date:
	try:
		return dt.date.fromisoformat(str(value))
	except (TypeError, ValueError):
		frappe.throw(frappe._(f"{label} must be an ISO date."))
