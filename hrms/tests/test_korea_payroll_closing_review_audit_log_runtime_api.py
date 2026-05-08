#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import json
import pathlib
import sys
import types
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "payroll_closing_review_audit_log_runtime_api.py"


def load_module_with_frappe_stub():
	frappe = types.ModuleType("frappe")
	frappe._ = lambda message: message
	frappe.whitelist = lambda: (lambda fn: fn)
	frappe.session = types.SimpleNamespace(user="hr.auditor@example.com")

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
		spec = importlib.util.spec_from_file_location("korea_payroll_closing_review_audit_log_runtime_api", MODULE_PATH)
		module = importlib.util.module_from_spec(spec)
		assert spec.loader is not None
		spec.loader.exec_module(module)
		return module, frappe
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


class TestKoreaPayrollClosingReviewAuditLogRuntimeApi(unittest.TestCase):
	def test_runtime_api_inserts_core_audit_log_json_with_session_actor_default(self):
		module, frappe = load_module_with_frappe_stub()
		inserted = []

		class FakeAuditLogDoc:
			def __init__(self, fields):
				self.fields = dict(fields)
				self.name = "KPCRA-0001"

			def insert(self):
				inserted.append(self)
				return self

		frappe.get_doc = lambda fields: FakeAuditLogDoc(fields)
		result = module.create_korea_payroll_closing_review_audit_log_runtime(audit_log=json.dumps(audit_log_preview()))

		self.assertEqual(len(inserted), 1)
		self.assertEqual(inserted[0].fields["doctype"], "Korea Payroll Closing Review Audit Log")
		self.assertEqual(inserted[0].fields["docstatus"], 0)
		self.assertEqual(result["contract_type"], "korea_payroll_closing_review_audit_log_runtime_insert_api_v1")
		self.assertEqual(result["runtime_insert_contract_type"], "korea_payroll_closing_review_audit_log_runtime_insert_v1")
		self.assertEqual(result["runtime_action"], "runtime_review_audit_log_created")
		self.assertFalse(result["requires_runtime_apply"])
		self.assertEqual(result["mutation_boundary"], "audit_log_only_no_submit_no_send_no_provider_call")
		self.assertEqual(result["audit_actor"], "hr.auditor@example.com")
		self.assertTrue(result["requires_human_approval"])
		self.assertEqual(result["ai_role"], "assistant_only")

	def test_runtime_api_rejects_preview_wrapper_invalid_json_and_defensively_copies(self):
		module, frappe = load_module_with_frappe_stub()
		frappe.get_doc = lambda fields: self.fail("invalid payload must fail before runtime insert")

		with self.assertRaisesRegex(ValueError, "JSON payload is invalid"):
			module.create_korea_payroll_closing_review_audit_log_runtime(audit_log='{"contract_type":')

		with self.assertRaisesRegex(ValueError, "audit_log must be a dict or JSON object"):
			module.create_korea_payroll_closing_review_audit_log_runtime(audit_log="[]")

		wrapped = audit_log_preview()
		wrapped["contract_type"] = "korea_payroll_closing_draft_review_audit_log_preview_v1"
		with self.assertRaisesRegex(ValueError, "audit_log.contract_type must be korea_payroll_closing_draft_review_audit_log_v1"):
			module.create_korea_payroll_closing_review_audit_log_runtime(audit_log=wrapped, audit_actor="hr.auditor@example.com")

		payload = audit_log_preview()
		original = copy.deepcopy(payload)

		class FakeAuditLogDoc:
			def __init__(self, fields):
				self.fields = dict(fields)
				self.name = "KPCRA-0002"

			def insert(self):
				return self

		frappe.get_doc = lambda fields: FakeAuditLogDoc(fields)
		result = module.create_korea_payroll_closing_review_audit_log_runtime(audit_log=payload, audit_actor="hr.auditor@example.com")
		result["source_audit_log_contract_type"] = "MUTATED"
		self.assertEqual(payload, original)


if __name__ == "__main__":
	unittest.main()
