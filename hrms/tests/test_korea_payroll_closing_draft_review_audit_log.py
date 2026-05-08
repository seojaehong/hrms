#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "payroll_closing_draft_review_audit_log.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_payroll_closing_draft_review_audit_log", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


def runtime_apply_result():
	return {
		"contract_type": "korea_payroll_closing_draft_review_runtime_apply_api_v1",
		"runtime_apply_contract_type": "korea_payroll_closing_draft_review_runtime_apply_v1",
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


class TestKoreaPayrollClosingDraftReviewAuditLog(unittest.TestCase):
	def test_builds_preview_audit_log_from_runtime_review_status_update(self):
		module = load_module()
		result = module.build_korea_payroll_closing_draft_review_audit_log(
			runtime_apply_result(),
			audit_actor="hr.auditor@example.com",
		)

		self.assertEqual(result["contract_type"], "korea_payroll_closing_draft_review_audit_log_v1")
		self.assertEqual(result["source_runtime_apply_contract_type"], "korea_payroll_closing_draft_review_runtime_apply_api_v1")
		self.assertEqual(result["runtime_apply_contract_type"], "korea_payroll_closing_draft_review_runtime_apply_v1")
		self.assertEqual(result["runtime_action"], "preview_only")
		self.assertTrue(result["requires_runtime_apply"])
		self.assertEqual(result["would_create_doctype"], "Korea Payroll Closing Review Audit Log")
		self.assertEqual(result["mutation_boundary"], "audit_log_only_no_submit_no_send_no_provider_call")
		self.assertEqual(result["draft_name"], "KPCD-0001")
		self.assertEqual(result["previous_status"], "draft_pending_human_approval")
		self.assertEqual(result["status"], "draft_human_approved")
		self.assertEqual(result["action"], "approve_draft")
		self.assertEqual(result["review_actor"], "hr.manager@example.com")
		self.assertEqual(result["audit_actor"], "hr.auditor@example.com")
		self.assertTrue(result["requires_human_approval"])
		self.assertEqual(result["ai_role"], "assistant_only")
		self.assertEqual(result["audit_event"]["event_type"], "korea_payroll_closing_draft_review_status_audit_v1")
		self.assertEqual(result["audit_event"]["company"], "Korea Demo Co")
		self.assertEqual(result["audit_event"]["workplace"], "Seoul HQ")
		self.assertEqual(result["audit_event"]["period_start"], "2026-05-01")
		self.assertEqual(result["audit_event"]["period_end"], "2026-05-31")
		self.assertEqual(result["audit_event"]["runtime_action"], "preview_only")
		self.assertTrue(result["audit_event"]["requires_runtime_apply"])
		self.assertEqual(result["audit_event"]["ai_role"], "assistant_only")

	def test_rejects_invalid_status_transition_and_numeric_score_keys(self):
		module = load_module()
		payload = runtime_apply_result()
		payload["status"] = "submitted"
		with self.assertRaisesRegex(ValueError, "status must be a guarded human-review result status"):
			module.build_korea_payroll_closing_draft_review_audit_log(payload, audit_actor="hr.auditor@example.com")

		payload = runtime_apply_result()
		payload["legalRiskScoreCandidate"] = 0.91
		with self.assertRaisesRegex(ValueError, "legalRiskScoreCandidate is not allowed"):
			module.build_korea_payroll_closing_draft_review_audit_log(payload, audit_actor="hr.auditor@example.com")

		payload = runtime_apply_result()
		payload["audit"] = {"legal": {"score": 0.91}}
		with self.assertRaisesRegex(ValueError, "score is not allowed"):
			module.build_korea_payroll_closing_draft_review_audit_log(payload, audit_actor="hr.auditor@example.com")

	def test_rejects_non_runtime_apply_contract_and_defensively_copies_source(self):
		module = load_module()
		payload = runtime_apply_result()
		payload["contract_type"] = "korea_payroll_closing_draft_review_action_preview_v1"
		with self.assertRaisesRegex(ValueError, "runtime_apply.contract_type must be"):
			module.build_korea_payroll_closing_draft_review_audit_log(payload, audit_actor="hr.auditor@example.com")

		payload = runtime_apply_result()
		payload["contract_type"] = "korea_payroll_closing_draft_review_runtime_apply_v1"
		payload["runtime_apply_contract_type"] = "evil_contract"
		with self.assertRaisesRegex(ValueError, "runtime_apply.runtime_apply_contract_type must be korea_payroll_closing_draft_review_runtime_apply_v1"):
			module.build_korea_payroll_closing_draft_review_audit_log(payload, audit_actor="hr.auditor@example.com")

		payload = runtime_apply_result()
		original = copy.deepcopy(payload)
		result = module.build_korea_payroll_closing_draft_review_audit_log(payload, audit_actor="hr.auditor@example.com")
		payload["status"] = "MUTATED"
		result["source_runtime_apply"]["status"] = "MUTATED_RESULT"
		self.assertEqual(original["status"], "draft_human_approved")
		self.assertEqual(result["audit_event"]["status"], "draft_human_approved")

	def test_rejects_invalid_period_and_actor_inputs_before_copying(self):
		module = load_module()
		payload = runtime_apply_result()
		payload["period_start"] = "2026-06-01"
		with self.assertRaisesRegex(ValueError, "period_start must be on or before period_end"):
			module.build_korea_payroll_closing_draft_review_audit_log(payload, audit_actor="hr.auditor@example.com")

		with self.assertRaisesRegex(ValueError, "audit_actor must be a non-empty string"):
			module.build_korea_payroll_closing_draft_review_audit_log(runtime_apply_result(), audit_actor="")

		payload = runtime_apply_result()
		payload["requires_human_approval"] = "true"
		with self.assertRaisesRegex(ValueError, "requires_human_approval must be true"):
			module.build_korea_payroll_closing_draft_review_audit_log(payload, audit_actor="hr.auditor@example.com")


if __name__ == "__main__":
	unittest.main()
