#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import json
import pathlib
import sys
import types
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "payroll_closing_draft_review_audit_log_api.py"


def load_module_with_frappe_stub():
	frappe_stub = types.ModuleType("frappe")

	def whitelist():
		def decorator(fn):
			fn.is_whitelisted_for_test = True
			return fn
		return decorator

	frappe_stub.whitelist = whitelist
	previous = sys.modules.get("frappe")
	sys.modules["frappe"] = frappe_stub
	try:
		spec = importlib.util.spec_from_file_location("korea_payroll_closing_draft_review_audit_log_api", MODULE_PATH)
		module = importlib.util.module_from_spec(spec)
		assert spec.loader is not None
		spec.loader.exec_module(module)
		return module
	finally:
		if previous is None:
			sys.modules.pop("frappe", None)
		else:
			sys.modules["frappe"] = previous


def runtime_apply_result():
	return {
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
	}


class TestKoreaPayrollClosingDraftReviewAuditLogApi(unittest.TestCase):
	def test_preview_api_wraps_core_audit_log_contract_without_mutation(self):
		module = load_module_with_frappe_stub()
		payload = runtime_apply_result()
		original = copy.deepcopy(payload)

		result = module.preview_korea_payroll_closing_draft_review_audit_log(
			runtime_apply=json.dumps(payload),
			audit_actor="hr.auditor@example.com",
		)
		payload["status"] = "MUTATED_CALLER"
		result["source_runtime_apply"]["status"] = "MUTATED_OUTPUT"

		self.assertEqual(result["contract_type"], "korea_payroll_closing_draft_review_audit_log_preview_v1")
		self.assertEqual(result["audit_log_contract_type"], "korea_payroll_closing_draft_review_audit_log_v1")
		self.assertEqual(result["source_runtime_apply_contract_type"], "korea_payroll_closing_draft_review_runtime_apply_v1")
		self.assertEqual(result["runtime_action"], "preview_only")
		self.assertTrue(result["requires_runtime_apply"])
		self.assertEqual(result["would_create_doctype"], "Korea Payroll Closing Review Audit Log")
		self.assertEqual(result["mutation_boundary"], "audit_log_only_no_submit_no_send_no_provider_call")
		self.assertTrue(result["requires_human_approval"])
		self.assertEqual(result["ai_role"], "assistant_only")
		self.assertEqual(result["audit_event"]["runtime_action"], "preview_only")
		self.assertEqual(result["audit_event"]["audit_actor"], "hr.auditor@example.com")
		self.assertEqual(original["status"], "draft_human_approved")
		self.assertEqual(result["audit_event"]["status"], "draft_human_approved")

	def test_preview_api_rejects_invalid_json_non_dict_and_preview_wrapper_input(self):
		module = load_module_with_frappe_stub()
		with self.assertRaisesRegex(ValueError, "JSON payload is invalid"):
			module.preview_korea_payroll_closing_draft_review_audit_log(
				runtime_apply='{"contract_type":',
				audit_actor="hr.auditor@example.com",
			)
		with self.assertRaisesRegex(ValueError, "runtime_apply must be a dict or JSON object"):
			module.preview_korea_payroll_closing_draft_review_audit_log(
				runtime_apply="[]",
				audit_actor="hr.auditor@example.com",
			)

		payload = runtime_apply_result()
		payload["contract_type"] = "korea_payroll_closing_draft_review_runtime_apply_api_v1"
		payload["runtime_apply_contract_type"] = "evil_contract"
		with self.assertRaisesRegex(ValueError, "runtime_apply.runtime_apply_contract_type must be korea_payroll_closing_draft_review_runtime_apply_v1"):
			module.preview_korea_payroll_closing_draft_review_audit_log(
				runtime_apply=payload,
				audit_actor="hr.auditor@example.com",
			)

	def test_preview_api_is_whitelisted_when_frappe_is_available_and_rejects_bad_actor(self):
		module = load_module_with_frappe_stub()
		self.assertTrue(module.preview_korea_payroll_closing_draft_review_audit_log.is_whitelisted_for_test)

		with self.assertRaisesRegex(ValueError, "audit_actor must be a non-empty string"):
			module.preview_korea_payroll_closing_draft_review_audit_log(
				runtime_apply=runtime_apply_result(),
				audit_actor=True,
			)


if __name__ == "__main__":
	unittest.main()
