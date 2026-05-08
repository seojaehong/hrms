#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import json
import pathlib
import sys
import types
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "payroll_closing_draft_review_runtime_api.py"


def load_module_with_frappe_stub():
	frappe = types.ModuleType("frappe")
	frappe._ = lambda message: message
	frappe.whitelist = lambda: (lambda fn: fn)
	frappe.session = types.SimpleNamespace(user="hr.manager@example.com")

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
		spec = importlib.util.spec_from_file_location("korea_payroll_closing_draft_review_runtime_api", MODULE_PATH)
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


def review_action():
	source_draft = {
		"contract_type": "korea_payroll_closing_draft_runtime_insert_v1",
		"source_apply_plan_contract_type": "korea_payroll_closing_draft_apply_plan_v1",
		"runtime_action": "runtime_draft_created",
		"requires_runtime_apply": False,
		"mutation_boundary": "draft_only_no_submit_no_approve_no_send",
		"doctype": "Korea Payroll Closing Draft",
		"name": "KPCD-0001",
		"status": "draft_pending_human_approval",
		"company": "Korea Demo Co",
		"workplace": "Seoul HQ",
		"period_start": "2026-05-01",
		"period_end": "2026-05-31",
		"source_payroll_entry": "PAY-ENTRY-2026-05",
		"approver": "hr.manager@example.com",
		"actor": "hr.ops@example.com",
		"docstatus": 0,
		"requires_human_approval": True,
		"ai_role": "assistant_only",
	}
	return {
		"contract_type": "korea_payroll_closing_draft_review_action_v1",
		"source_draft_contract_type": "korea_payroll_closing_draft_runtime_insert_v1",
		"runtime_action": "preview_only",
		"requires_runtime_apply": True,
		"mutation_boundary": "human_review_only_no_submit_no_send_no_provider_call",
		"would_update_doctype": "Korea Payroll Closing Draft",
		"would_update_name": "KPCD-0001",
		"would_set_status": "draft_human_approved",
		"action": "approve_draft",
		"actor": "hr.manager@example.com",
		"note": "Reviewed statutory basis and evidence packet.",
		"company": "Korea Demo Co",
		"workplace": "Seoul HQ",
		"period_start": "2026-05-01",
		"period_end": "2026-05-31",
		"source_payroll_entry": "PAY-ENTRY-2026-05",
		"source_draft": source_draft,
		"audit_preview": {
			"event_type": "korea_payroll_closing_draft_human_review_v1",
			"runtime_action": "preview_only",
			"requires_runtime_apply": True,
			"mutation_boundary": "human_review_only_no_submit_no_send_no_provider_call",
			"company": "Korea Demo Co",
			"workplace": "Seoul HQ",
			"period_start": "2026-05-01",
			"period_end": "2026-05-31",
			"draft_name": "KPCD-0001",
			"source_payroll_entry": "PAY-ENTRY-2026-05",
			"previous_status": "draft_pending_human_approval",
			"would_set_status": "draft_human_approved",
			"action": "approve_draft",
			"actor": "hr.manager@example.com",
			"note": "Reviewed statutory basis and evidence packet.",
			"requires_human_approval": True,
			"ai_role": "assistant_only",
		},
		"requires_human_approval": True,
		"ai_role": "assistant_only",
	}


class TestKoreaPayrollClosingDraftReviewRuntimeApi(unittest.TestCase):
	def test_runtime_api_applies_core_review_action_json_with_session_actor_default(self):
		module, frappe = load_module_with_frappe_stub()
		inserted = []

		class FakeDraftDoc:
			name = "KPCD-0001"
			company = "Korea Demo Co"
			workplace = "Seoul HQ"
			period_start = "2026-05-01"
			period_end = "2026-05-31"
			source_payroll_entry = "PAY-ENTRY-2026-05"
			approver = "hr.manager@example.com"
			status = "draft_pending_human_approval"
			docstatus = 0
			requires_human_approval = 1
			ai_role = "assistant_only"
			mutation_boundary = "draft_only_no_submit_no_approve_no_send"

			def save(self):
				inserted.append(self)
				return self

		frappe.get_doc = lambda doctype, name: FakeDraftDoc()
		result = module.apply_korea_payroll_closing_draft_review_runtime(review_action=json.dumps(review_action()))

		self.assertEqual(len(inserted), 1)
		self.assertEqual(inserted[0].status, "draft_human_approved")
		self.assertEqual(result["contract_type"], "korea_payroll_closing_draft_review_runtime_apply_api_v1")
		self.assertEqual(result["runtime_apply_contract_type"], "korea_payroll_closing_draft_review_runtime_apply_v1")
		self.assertEqual(result["runtime_action"], "runtime_draft_review_status_updated")
		self.assertFalse(result["requires_runtime_apply"])
		self.assertEqual(result["mutation_boundary"], "human_review_status_only_no_submit_no_send_no_provider_call")
		self.assertEqual(result["actor"], "hr.manager@example.com")
		self.assertTrue(result["requires_human_approval"])
		self.assertEqual(result["ai_role"], "assistant_only")

	def test_runtime_api_rejects_preview_wrapper_invalid_json_and_defensively_copies(self):
		module, frappe = load_module_with_frappe_stub()
		frappe.get_doc = lambda doctype, name: self.fail("invalid payload must fail before runtime lookup")

		with self.assertRaisesRegex(ValueError, "JSON payload is invalid"):
			module.apply_korea_payroll_closing_draft_review_runtime(review_action='{"contract_type":')

		with self.assertRaisesRegex(ValueError, "review_action must be a dict or JSON object"):
			module.apply_korea_payroll_closing_draft_review_runtime(review_action="[]")

		wrapped = review_action()
		wrapped["contract_type"] = "korea_payroll_closing_draft_review_action_preview_v1"
		with self.assertRaisesRegex(ValueError, "review_action.contract_type must be korea_payroll_closing_draft_review_action_v1"):
			module.apply_korea_payroll_closing_draft_review_runtime(review_action=wrapped)

		action = review_action()
		original = copy.deepcopy(action)
		class FakeDraftDoc:
			name = "KPCD-0001"
			company = "Korea Demo Co"
			workplace = "Seoul HQ"
			period_start = "2026-05-01"
			period_end = "2026-05-31"
			source_payroll_entry = "PAY-ENTRY-2026-05"
			approver = "hr.manager@example.com"
			status = "draft_pending_human_approval"
			docstatus = 0
			requires_human_approval = 1
			ai_role = "assistant_only"
			mutation_boundary = "draft_only_no_submit_no_approve_no_send"
			def save(self):
				return self
		frappe.get_doc = lambda doctype, name: FakeDraftDoc()
		result = module.apply_korea_payroll_closing_draft_review_runtime(review_action=action, actor="hr.manager@example.com")
		result["source_review_action_contract_type"] = "MUTATED"
		self.assertEqual(action, original)


if __name__ == "__main__":
	unittest.main()
