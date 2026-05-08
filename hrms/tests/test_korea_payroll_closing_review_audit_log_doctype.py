#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCTYPE_DIR = ROOT / "hr" / "doctype" / "korea_payroll_closing_review_audit_log"
JSON_PATH = DOCTYPE_DIR / "korea_payroll_closing_review_audit_log.json"
PY_PATH = DOCTYPE_DIR / "korea_payroll_closing_review_audit_log.py"


def load_schema():
	with JSON_PATH.open(encoding="utf-8") as handle:
		return json.load(handle)


def load_controller_with_frappe_stub():
	frappe = types.ModuleType("frappe")
	frappe._ = lambda message: message

	def throw(message):
		raise ValueError(message)

	frappe.throw = throw
	model = types.ModuleType("frappe.model")
	document = types.ModuleType("frappe.model.document")

	class Document:
		pass

	document.Document = Document
	stubbed_names = ["frappe", "frappe.model", "frappe.model.document"]
	previous_modules = {name: sys.modules.get(name) for name in stubbed_names}
	sys.modules["frappe"] = frappe
	sys.modules["frappe.model"] = model
	sys.modules["frappe.model.document"] = document
	try:
		spec = importlib.util.spec_from_file_location("korea_payroll_closing_review_audit_log_doctype", PY_PATH)
		module = importlib.util.module_from_spec(spec)
		assert spec.loader is not None
		spec.loader.exec_module(module)
		return module
	finally:
		for name in stubbed_names:
			if previous_modules[name] is None:
				sys.modules.pop(name, None)
			else:
				sys.modules[name] = previous_modules[name]


def audit_log_preview():
	return {
		"contract_type": "korea_payroll_closing_draft_review_audit_log_v1",
		"source_runtime_apply_contract_type": "korea_payroll_closing_draft_review_runtime_apply_v1",
		"runtime_apply_contract_type": "korea_payroll_closing_draft_review_runtime_apply_v1",
		"source_review_action_contract_type": "korea_payroll_closing_draft_review_action_v1",
		"runtime_action": "preview_only",
		"requires_runtime_apply": True,
		"would_create_doctype": "Korea Payroll Closing Review Audit Log",
		"mutation_boundary": "audit_log_only_no_submit_no_send_no_provider_call",
		"draft_name": "KPCD-0001",
		"previous_status": "draft_pending_human_approval",
		"status": "draft_human_approved",
		"action": "approve_draft",
		"review_actor": "hr.manager@example.com",
		"audit_actor": "hr.auditor@example.com",
		"company": "Korea Demo Co",
		"workplace": "Seoul HQ",
		"period_start": "2026-05-01",
		"period_end": "2026-05-31",
		"source_payroll_entry": "PAY-ENTRY-2026-05",
		"audit_event": {
			"event_type": "korea_payroll_closing_draft_review_status_audit_v1",
			"runtime_action": "preview_only",
			"requires_runtime_apply": True,
			"mutation_boundary": "audit_log_only_no_submit_no_send_no_provider_call",
			"would_create_doctype": "Korea Payroll Closing Review Audit Log",
			"draft_name": "KPCD-0001",
			"previous_status": "draft_pending_human_approval",
			"status": "draft_human_approved",
			"action": "approve_draft",
			"review_actor": "hr.manager@example.com",
			"audit_actor": "hr.auditor@example.com",
			"company": "Korea Demo Co",
			"workplace": "Seoul HQ",
			"period_start": "2026-05-01",
			"period_end": "2026-05-31",
			"source_payroll_entry": "PAY-ENTRY-2026-05",
			"requires_human_approval": True,
			"ai_role": "assistant_only",
		},
		"source_runtime_apply": {
			"contract_type": "korea_payroll_closing_draft_review_runtime_apply_v1",
			"source_review_action_contract_type": "korea_payroll_closing_draft_review_action_v1",
			"runtime_action": "runtime_draft_review_status_updated",
			"requires_runtime_apply": False,
			"mutation_boundary": "human_review_status_only_no_submit_no_send_no_provider_call",
			"doctype": "Korea Payroll Closing Draft",
			"name": "KPCD-0001",
			"previous_status": "draft_pending_human_approval",
			"status": "draft_human_approved",
			"action": "approve_draft",
			"actor": "hr.manager@example.com",
			"company": "Korea Demo Co",
			"workplace": "Seoul HQ",
			"period_start": "2026-05-01",
			"period_end": "2026-05-31",
			"source_payroll_entry": "PAY-ENTRY-2026-05",
			"requires_human_approval": True,
			"ai_role": "assistant_only",
		},
		"requires_human_approval": True,
		"ai_role": "assistant_only",
	}


class TestKoreaPayrollClosingReviewAuditLogDoctype(unittest.TestCase):
	def test_schema_defines_audit_log_runtime_persistence_boundary(self):
		schema = load_schema()
		fields = {field["fieldname"]: field for field in schema["fields"] if "fieldname" in field}

		self.assertEqual(schema["name"], "Korea Payroll Closing Review Audit Log")
		self.assertEqual(schema["module"], "HR")
		self.assertEqual(schema.get("is_submittable", 0), 0)
		self.assertEqual(schema["title_field"], "draft_name")
		for key in ["delete", "email", "share"]:
			self.assertEqual(schema["permissions"][0].get(key, 0), 0)

		for fieldname, fieldtype, options in [
			("company", "Link", "Company"),
			("period_start", "Date", None),
			("period_end", "Date", None),
			("draft_name", "Link", "Korea Payroll Closing Draft"),
			("source_payroll_entry", "Link", "Payroll Entry"),
			("review_actor", "Link", "User"),
			("audit_actor", "Link", "User"),
			("audit_event", "Long Text", None),
			("source_runtime_apply", "Long Text", None),
		]:
			with self.subTest(fieldname=fieldname):
				self.assertIn(fieldname, fields)
				self.assertEqual(fields[fieldname]["fieldtype"], fieldtype)
				self.assertEqual(fields[fieldname].get("reqd"), 1)
				if options:
					self.assertEqual(fields[fieldname].get("options"), options)

		self.assertEqual(fields["workplace"]["fieldtype"], "Data")
		self.assertEqual(fields["status"].get("options"), "draft_human_approved\ndraft_human_rejected\ndraft_changes_requested")
		self.assertEqual(fields["action"].get("options"), "approve_draft\nreject_draft\nrequest_changes")
		self.assertEqual(fields["mutation_boundary"].get("default"), "audit_log_only_no_submit_no_send_no_provider_call")
		self.assertEqual(fields["source_audit_log_contract_type"].get("default"), "korea_payroll_closing_draft_review_audit_log_v1")
		self.assertEqual(fields["requires_human_approval"].get("default"), "1")
		self.assertEqual(fields["ai_role"].get("default"), "assistant_only")

		permissions = {perm["role"]: perm for perm in schema["permissions"]}
		self.assertEqual({key: permissions["HR Manager"].get(key, 0) for key in ["create", "read", "write", "delete", "email", "share"]}, {"create": 1, "read": 1, "write": 0, "delete": 0, "email": 0, "share": 0})
		self.assertEqual({key: permissions["HR User"].get(key, 0) for key in ["create", "read", "write", "delete", "email", "share"]}, {"create": 0, "read": 1, "write": 0, "delete": 0, "email": 0, "share": 0})
		self.assertNotIn("Employee", permissions)

	def test_controller_validates_scope_and_safety_boundaries(self):
		module = load_controller_with_frappe_stub()
		doc = module.KoreaPayrollClosingReviewAuditLog()
		doc.company = " Korea Demo Co "
		doc.workplace = " Seoul HQ "
		doc.period_start = "2026-05-01"
		doc.period_end = "2026-05-31"
		doc.draft_name = "KPCD-0001"
		doc.source_payroll_entry = "PAY-ENTRY-2026-05"
		doc.previous_status = "draft_pending_human_approval"
		doc.status = "draft_human_approved"
		doc.action = "approve_draft"
		doc.review_actor = "hr.manager@example.com"
		doc.audit_actor = "hr.auditor@example.com"
		doc.source_audit_log_contract_type = "korea_payroll_closing_draft_review_audit_log_v1"
		doc.mutation_boundary = "audit_log_only_no_submit_no_send_no_provider_call"
		doc.requires_human_approval = 1
		doc.ai_role = "assistant_only"
		doc.audit_event = json.dumps(audit_log_preview()["audit_event"], indent=2)
		doc.source_runtime_apply = json.dumps(audit_log_preview()["source_runtime_apply"], indent=2)

		doc.validate()

		self.assertEqual(doc.company, "Korea Demo Co")
		self.assertEqual(doc.workplace, "Seoul HQ")
		self.assertEqual(json.loads(doc.audit_event)["company"], "Korea Demo Co")
		self.assertEqual(json.loads(doc.source_runtime_apply)["name"], "KPCD-0001")

		doc.status = "submitted"
		with self.assertRaisesRegex(ValueError, "status must stay within guarded human-review audit states"):
			doc.validate()

		doc.status = "draft_human_approved"
		doc.audit_event = json.dumps({"company": "Other Co", "workplace": "Seoul HQ", "period_start": "2026-05-01", "period_end": "2026-05-31", "draft_name": "KPCD-0001", "status": "draft_human_approved", "action": "approve_draft"})
		with self.assertRaisesRegex(ValueError, "Audit event company must match the audit log company"):
			doc.validate()

	def test_runtime_adapter_inserts_only_audit_log_without_submit_or_send(self):
		module = load_controller_with_frappe_stub()
		inserted_docs = []

		class FakeAuditLogDoc:
			def __init__(self, fields):
				self.fields = dict(fields)
				self.name = "KPCRA-0001"
				self.submitted = False

			def insert(self):
				inserted_docs.append(self)
				return self

		def fake_get_doc(fields):
			return FakeAuditLogDoc(fields)

		module.frappe.get_doc = fake_get_doc
		result = module.create_korea_payroll_closing_review_audit_log(
			audit_log_preview(),
			audit_actor="hr.auditor@example.com",
		)

		self.assertEqual(len(inserted_docs), 1)
		created_fields = inserted_docs[0].fields
		self.assertEqual(created_fields["doctype"], "Korea Payroll Closing Review Audit Log")
		self.assertEqual(created_fields["docstatus"], 0)
		self.assertEqual(created_fields["mutation_boundary"], "audit_log_only_no_submit_no_send_no_provider_call")
		self.assertEqual(created_fields["requires_human_approval"], 1)
		self.assertEqual(created_fields["ai_role"], "assistant_only")
		self.assertEqual(created_fields["audit_actor"], "hr.auditor@example.com")
		self.assertIsInstance(created_fields["audit_event"], str)
		self.assertIsInstance(created_fields["source_runtime_apply"], str)
		self.assertEqual(json.loads(created_fields["audit_event"])["status"], "draft_human_approved")
		self.assertEqual(result["contract_type"], "korea_payroll_closing_review_audit_log_runtime_insert_v1")
		self.assertEqual(result["runtime_action"], "runtime_review_audit_log_created")
		self.assertFalse(result["requires_runtime_apply"])
		self.assertEqual(result["doctype"], "Korea Payroll Closing Review Audit Log")
		self.assertEqual(result["name"], "KPCRA-0001")

	def test_runtime_adapter_rejects_preview_wrapper_and_score_keys_before_insert(self):
		module = load_controller_with_frappe_stub()
		module.frappe.get_doc = lambda fields: self.fail("invalid audit log must not be inserted")

		payload = audit_log_preview()
		payload["contract_type"] = "korea_payroll_closing_draft_review_audit_log_preview_v1"
		with self.assertRaisesRegex(ValueError, "audit_log.contract_type must be korea_payroll_closing_draft_review_audit_log_v1"):
			module.create_korea_payroll_closing_review_audit_log(payload, audit_actor="hr.auditor@example.com")

		payload = audit_log_preview()
		payload["audit_event"]["legal"] = {"score": 0.91}
		with self.assertRaisesRegex(ValueError, "audit_event must not contain numeric risk/probability/success-rate score fields"):
			module.create_korea_payroll_closing_review_audit_log(payload, audit_actor="hr.auditor@example.com")

		payload = audit_log_preview()
		payload["source_runtime_apply"]["legal"] = {"score": 0.91}
		with self.assertRaisesRegex(ValueError, "source_runtime_apply must not contain numeric risk/probability/success-rate score fields"):
			module.create_korea_payroll_closing_review_audit_log(payload, audit_actor="hr.auditor@example.com")

		payload = audit_log_preview()
		with self.assertRaisesRegex(ValueError, "audit_log.audit_actor must match audit_actor"):
			module.create_korea_payroll_closing_review_audit_log(payload, audit_actor="other.auditor@example.com")

	def test_runtime_adapter_rejects_forged_embedded_contract_metadata(self):
		module = load_controller_with_frappe_stub()
		module.frappe.get_doc = lambda fields: self.fail("invalid embedded contracts must not be inserted")

		payload = audit_log_preview()
		payload["audit_event"]["runtime_action"] = "runtime_submit_payroll"
		with self.assertRaisesRegex(ValueError, "audit_event.runtime_action must be preview_only"):
			module.create_korea_payroll_closing_review_audit_log(payload, audit_actor="hr.auditor@example.com")

		payload = audit_log_preview()
		payload["audit_event"]["requires_human_approval"] = False
		with self.assertRaisesRegex(ValueError, "audit_event.requires_human_approval must be true"):
			module.create_korea_payroll_closing_review_audit_log(payload, audit_actor="hr.auditor@example.com")

		payload = audit_log_preview()
		payload["source_runtime_apply"]["runtime_action"] = "submit_payroll"
		with self.assertRaisesRegex(ValueError, "source_runtime_apply.runtime_action must be runtime_draft_review_status_updated"):
			module.create_korea_payroll_closing_review_audit_log(payload, audit_actor="hr.auditor@example.com")

		payload = audit_log_preview()
		payload["source_runtime_apply"]["mutation_boundary"] = "submit_and_send"
		with self.assertRaisesRegex(ValueError, "source_runtime_apply.mutation_boundary must remain human_review_status_only_no_submit_no_send_no_provider_call"):
			module.create_korea_payroll_closing_review_audit_log(payload, audit_actor="hr.auditor@example.com")

		payload = audit_log_preview()
		payload["source_runtime_apply"]["ai_role"] = "autonomous_agent"
		with self.assertRaisesRegex(ValueError, "source_runtime_apply.ai_role must be assistant_only"):
			module.create_korea_payroll_closing_review_audit_log(payload, audit_actor="hr.auditor@example.com")

	def test_controller_rejects_forged_embedded_contract_metadata_on_direct_insert(self):
		module = load_controller_with_frappe_stub()
		doc = module.KoreaPayrollClosingReviewAuditLog()
		doc.company = "Korea Demo Co"
		doc.workplace = "Seoul HQ"
		doc.period_start = "2026-05-01"
		doc.period_end = "2026-05-31"
		doc.draft_name = "KPCD-0001"
		doc.source_payroll_entry = "PAY-ENTRY-2026-05"
		doc.previous_status = "draft_pending_human_approval"
		doc.status = "draft_human_approved"
		doc.action = "approve_draft"
		doc.review_actor = "hr.manager@example.com"
		doc.audit_actor = "hr.auditor@example.com"
		doc.source_audit_log_contract_type = "korea_payroll_closing_draft_review_audit_log_v1"
		doc.mutation_boundary = "audit_log_only_no_submit_no_send_no_provider_call"
		doc.requires_human_approval = 1
		doc.ai_role = "assistant_only"
		doc.audit_event = json.dumps(audit_log_preview()["audit_event"])
		forged_runtime_apply = audit_log_preview()["source_runtime_apply"]
		forged_runtime_apply["requires_runtime_apply"] = True
		doc.source_runtime_apply = json.dumps(forged_runtime_apply)

		with self.assertRaisesRegex(ValueError, "source_runtime_apply.requires_runtime_apply must be false"):
			doc.validate()


if __name__ == "__main__":
	unittest.main()
