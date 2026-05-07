#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCTYPE_DIR = ROOT / "hr" / "doctype" / "korea_payroll_closing_draft"
JSON_PATH = DOCTYPE_DIR / "korea_payroll_closing_draft.json"
PY_PATH = DOCTYPE_DIR / "korea_payroll_closing_draft.py"


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
		spec = importlib.util.spec_from_file_location("korea_payroll_closing_draft_doctype", PY_PATH)
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


class TestKoreaPayrollClosingDraftDoctype(unittest.TestCase):
	def test_schema_defines_draft_runtime_persistence_boundary(self):
		schema = load_schema()
		fields = {field["fieldname"]: field for field in schema["fields"] if "fieldname" in field}

		self.assertEqual(schema["name"], "Korea Payroll Closing Draft")
		self.assertEqual(schema["module"], "HR")
		self.assertEqual(schema.get("is_submittable", 0), 0)
		self.assertEqual(schema["title_field"], "source_payroll_entry")
		self.assertEqual(schema["sort_field"], "modified")
		self.assertEqual(schema["sort_order"], "DESC")

		for fieldname, fieldtype, options in [
			("company", "Link", "Company"),
			("period_start", "Date", None),
			("period_end", "Date", None),
			("source_payroll_entry", "Link", "Payroll Entry"),
			("approver", "Link", "User"),
			("payload", "Long Text", None),
			("audit_preview", "Long Text", None),
		]:
			with self.subTest(fieldname=fieldname):
				self.assertIn(fieldname, fields)
				self.assertEqual(fields[fieldname]["fieldtype"], fieldtype)
				self.assertEqual(fields[fieldname].get("reqd"), 1)
				if options:
					self.assertEqual(fields[fieldname].get("options"), options)

		self.assertEqual(fields["workplace"]["fieldtype"], "Data")
		self.assertEqual(fields["workplace"].get("reqd"), 1)
		self.assertEqual(fields["status"]["fieldtype"], "Select")
		self.assertEqual(fields["status"].get("default"), "draft_pending_human_approval")
		self.assertIn("draft_pending_human_approval", fields["status"].get("options", ""))
		self.assertEqual(fields["mutation_boundary"].get("default"), "draft_only_no_submit_no_approve_no_send")
		self.assertEqual(fields["source_session_contract_type"].get("default"), "korea_payroll_closing_session_v1")
		self.assertEqual(fields["requires_human_approval"].get("default"), "1")
		self.assertEqual(fields["ai_role"].get("default"), "assistant_only")

		permissions = {perm["role"]: perm for perm in schema["permissions"]}
		self.assertEqual(
			{key: permissions["HR Manager"].get(key, 0) for key in ["create", "read", "write", "delete", "email", "share"]},
			{"create": 1, "read": 1, "write": 1, "delete": 0, "email": 0, "share": 0},
		)
		self.assertEqual(
			{key: permissions["HR User"].get(key, 0) for key in ["create", "read", "write", "delete", "email", "share"]},
			{"create": 0, "read": 1, "write": 0, "delete": 0, "email": 0, "share": 0},
		)
		self.assertNotIn("Employee", permissions)

	def test_controller_rejects_submit_or_autonomous_boundaries_and_normalizes_json_payload(self):
		module = load_controller_with_frappe_stub()
		doc = module.KoreaPayrollClosingDraft()
		doc.company = "Korea Demo Co"
		doc.workplace = "Seoul HQ"
		doc.period_start = "2026-05-01"
		doc.period_end = "2026-05-31"
		doc.status = "draft_pending_human_approval"
		doc.source_session_contract_type = "korea_payroll_closing_session_v1"
		doc.mutation_boundary = "draft_only_no_submit_no_approve_no_send"
		doc.requires_human_approval = 1
		doc.ai_role = "assistant_only"
		doc.payload = json.dumps({"session": {"company": "Korea Demo Co", "workplace": "Seoul HQ", "period_start": "2026-05-01", "period_end": "2026-05-31"}}, indent=2)
		doc.audit_preview = json.dumps({"runtime_action": "preview_only", "company": "Korea Demo Co", "workplace": "Seoul HQ", "period_start": "2026-05-01", "period_end": "2026-05-31"})

		doc.validate()

		self.assertEqual(doc.company, "Korea Demo Co")
		self.assertEqual(doc.workplace, "Seoul HQ")
		self.assertEqual(json.loads(doc.payload)["session"]["company"], "Korea Demo Co")
		self.assertEqual(json.loads(doc.audit_preview)["runtime_action"], "preview_only")

		doc.status = "submitted"
		with self.assertRaisesRegex(ValueError, "Korea Payroll Closing Draft stays draft_pending_human_approval"):
			doc.validate()

		doc.status = "draft_pending_human_approval"
		doc.ai_role = "autonomous_agent"
		with self.assertRaisesRegex(ValueError, "AI role must be assistant_only"):
			doc.validate()

		doc.ai_role = "assistant_only"
		doc.mutation_boundary = "submit_and_send"
		with self.assertRaisesRegex(ValueError, "Mutation boundary must remain draft_only_no_submit_no_approve_no_send"):
			doc.validate()

		doc.mutation_boundary = "draft_only_no_submit_no_approve_no_send"
		doc.payload = '{"session":'
		with self.assertRaisesRegex(ValueError, "Payload must be valid JSON"):
			doc.validate()

	def test_controller_rejects_reversed_period_and_payload_scope_mismatch(self):
		module = load_controller_with_frappe_stub()
		doc = self._valid_doc(module)
		doc.period_start = "2026-06-01"
		doc.period_end = "2026-05-31"
		with self.assertRaisesRegex(ValueError, "Period start must be on or before period end"):
			doc.validate()

		doc = self._valid_doc(module)
		doc.payload = json.dumps({"session": {"company": "Other Co", "workplace": "Seoul HQ"}})
		with self.assertRaisesRegex(ValueError, "Payload session company must match the draft company"):
			doc.validate()

		doc = self._valid_doc(module)
		doc.payload = json.dumps({"unscoped": True})
		with self.assertRaisesRegex(ValueError, "Payload session must be a JSON object"):
			doc.validate()

		doc = self._valid_doc(module)
		doc.audit_preview = json.dumps({"runtime_action": "preview_only", "company": "Korea Demo Co", "workplace": "Busan Branch", "period_start": "2026-05-01", "period_end": "2026-05-31"})
		with self.assertRaisesRegex(ValueError, "Audit preview workplace must match the draft workplace"):
			doc.validate()

		doc = self._valid_doc(module)
		doc.audit_preview = json.dumps({"runtime_action": "preview_only"})
		with self.assertRaisesRegex(ValueError, "Audit preview company is required"):
			doc.validate()

	def test_controller_rejects_forbidden_numeric_score_keys_in_embedded_json(self):
		module = load_controller_with_frappe_stub()

		doc = self._valid_doc(module)
		doc.payload = json.dumps(
			{
				"session": {
					"company": "Korea Demo Co",
					"workplace": "Seoul HQ",
					"period_start": "2026-05-01",
					"period_end": "2026-05-31",
					"payroll_artifacts": {"statutory_totals": {"risk_score": 0.82}},
				}
			}
		)
		with self.assertRaisesRegex(ValueError, "Payload must not contain numeric risk/probability/success-rate score fields"):
			doc.validate()

		doc = self._valid_doc(module)
		doc.payload = json.dumps(
			{
				"session": {
					"company": "Korea Demo Co",
					"workplace": "Seoul HQ",
					"period_start": "2026-05-01",
					"period_end": "2026-05-31",
					"approval": {"legalRiskScoreCandidate": "high"},
				}
			}
		)
		with self.assertRaisesRegex(ValueError, "Payload must not contain numeric risk/probability/success-rate score fields"):
			doc.validate()

		doc = self._valid_doc(module)
		doc.audit_preview = json.dumps(
			{
				"runtime_action": "preview_only",
				"company": "Korea Demo Co",
				"workplace": "Seoul HQ",
				"period_start": "2026-05-01",
				"period_end": "2026-05-31",
				"closing success rate": 99,
			}
		)
		with self.assertRaisesRegex(ValueError, "Audit Preview must not contain numeric risk/probability/success-rate score fields"):
			doc.validate()

		doc = self._valid_doc(module)
		doc.audit_preview = json.dumps(
			{
				"runtime_action": "preview_only",
				"company": "Korea Demo Co",
				"workplace": "Seoul HQ",
				"period_start": "2026-05-01",
				"period_end": "2026-05-31",
				"probabilityScorePct": 75,
			}
		)
		with self.assertRaisesRegex(ValueError, "Audit Preview must not contain numeric risk/probability/success-rate score fields"):
			doc.validate()

		doc = self._valid_doc(module)
		doc.payload = json.dumps(
			{
				"session": {
					"company": "Korea Demo Co",
					"workplace": "Seoul HQ",
					"period_start": "2026-05-01",
					"period_end": "2026-05-31",
					"legal": {"score": 0.91},
				}
			}
		)
		with self.assertRaisesRegex(ValueError, "Payload must not contain numeric risk/probability/success-rate score fields"):
			doc.validate()

	def _valid_doc(self, module):
		doc = module.KoreaPayrollClosingDraft()
		doc.company = "Korea Demo Co"
		doc.workplace = "Seoul HQ"
		doc.period_start = "2026-05-01"
		doc.period_end = "2026-05-31"
		doc.status = "draft_pending_human_approval"
		doc.source_session_contract_type = "korea_payroll_closing_session_v1"
		doc.mutation_boundary = "draft_only_no_submit_no_approve_no_send"
		doc.requires_human_approval = 1
		doc.ai_role = "assistant_only"
		doc.payload = json.dumps(
			{"session": {"company": "Korea Demo Co", "workplace": "Seoul HQ", "period_start": "2026-05-01", "period_end": "2026-05-31"}}
		)
		doc.audit_preview = json.dumps(
			{"runtime_action": "preview_only", "company": "Korea Demo Co", "workplace": "Seoul HQ", "period_start": "2026-05-01", "period_end": "2026-05-31"}
		)
		return doc


if __name__ == "__main__":
	unittest.main()
