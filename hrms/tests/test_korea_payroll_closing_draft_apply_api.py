#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import json
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "payroll_closing_draft_apply_api.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_payroll_closing_draft_apply_api", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


def draft_payload():
	return {
		"contract_type": "korea_payroll_closing_draft_v1",
		"doctype": "Korea Payroll Closing Draft",
		"runtime_action": "create_draft",
		"requires_runtime_apply": True,
		"mutation_boundary": "draft_only_no_submit_no_approve_no_send",
		"company": "Korea Demo Co",
		"workplace": "Seoul HQ",
		"period_start": "2026-05-01",
		"period_end": "2026-05-31",
		"status": "draft_pending_human_approval",
		"source_session_contract_type": "korea_payroll_closing_session_v1",
		"source_payroll_entry": "PAY-ENTRY-0001",
		"approver": "branch-manager@example.com",
		"actor": "hr-ops@example.com",
		"payload": {
			"session": {
				"contract_type": "korea_payroll_closing_session_v1",
				"company": "Korea Demo Co",
				"workplace": "Seoul HQ",
				"period_start": "2026-05-01",
				"period_end": "2026-05-31",
				"status": "review_ready",
				"blockers": [],
				"requires_human_approval": True,
				"ai_role": "assistant_only",
			},
			"payroll_artifacts": {"payroll_entry": "PAY-ENTRY-0001", "salary_slip_count": 2},
			"approval_state": {"approver": "branch-manager@example.com", "status": "pending_review"},
			"notification_state": {"payslip_artifacts_ready": True, "kakao_queue_ready": True},
			"readiness_cards": [{"key": "attendance", "status": "ready"}],
			"review_checklist": [
				{
					"key": "attendance_reviewed",
					"source_card": "attendance",
					"checked": True,
					"requires_human_review": True,
					"ai_role": "assistant_only",
				}
			],
			"next_actions": [{"action": "create_runtime_draft", "enabled": True}],
			"audit_preview": {
				"event_type": "korea_payroll_closing_session_review_v1",
				"runtime_action": "preview_only",
				"requires_runtime_apply": True,
				"company": "Korea Demo Co",
				"workplace": "Seoul HQ",
				"period_start": "2026-05-01",
				"period_end": "2026-05-31",
				"status": "review_ready",
				"blocker_codes": [],
			},
		},
		"requires_human_approval": True,
		"ai_role": "assistant_only",
	}


class TestKoreaPayrollClosingDraftApplyApi(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()

	def test_preview_api_builds_runtime_apply_plan_from_json_draft(self):
		draft = draft_payload()

		plan = self.mod.preview_korea_payroll_closing_draft_apply_plan(
			draft=json.dumps(draft),
			actor="payroll-ops@example.com",
		)

		self.assertEqual(plan["contract_type"], "korea_payroll_closing_draft_apply_plan_preview_v1")
		self.assertEqual(plan["apply_plan_contract_type"], "korea_payroll_closing_draft_apply_plan_v1")
		self.assertEqual(plan["source_draft_contract_type"], "korea_payroll_closing_draft_v1")
		self.assertEqual(plan["runtime_action"], "preview_only")
		self.assertTrue(plan["requires_runtime_apply"])
		self.assertEqual(plan["would_create_doctype"], "Korea Payroll Closing Draft")
		self.assertEqual(plan["docstatus"], 0)
		self.assertEqual(plan["mutation_boundary"], "draft_only_no_submit_no_approve_no_send")
		self.assertEqual(plan["actor"], "payroll-ops@example.com")
		self.assertEqual(plan["field_values"]["source_payroll_entry"], "PAY-ENTRY-0001")
		self.assertTrue(plan["requires_human_approval"])
		self.assertEqual(plan["ai_role"], "assistant_only")

	def test_preview_api_does_not_mutate_caller_draft_or_alias_output(self):
		draft = draft_payload()
		original = copy.deepcopy(draft)

		plan = self.mod.preview_korea_payroll_closing_draft_apply_plan(draft=draft, actor="payroll-ops@example.com")

		self.assertEqual(draft, original)
		plan["field_values"]["payload"]["payroll_artifacts"]["payroll_entry"] = "MUTATED"
		self.assertEqual(draft["payload"]["payroll_artifacts"]["payroll_entry"], "PAY-ENTRY-0001")

	def test_invalid_json_and_non_dict_draft_are_rejected_before_delegation(self):
		with self.assertRaisesRegex(ValueError, "JSON payload is invalid"):
			self.mod.preview_korea_payroll_closing_draft_apply_plan(draft='{"contract_type":', actor="payroll-ops@example.com")

		with self.assertRaisesRegex(ValueError, "draft must be a dict or JSON object"):
			self.mod.preview_korea_payroll_closing_draft_apply_plan(draft="[]", actor="payroll-ops@example.com")

	def test_preview_api_rejects_preview_wrapper_instead_of_core_draft_contract(self):
		draft = draft_payload()
		draft["contract_type"] = "korea_payroll_closing_draft_preview_v1"

		with self.assertRaisesRegex(ValueError, "draft.contract_type must be korea_payroll_closing_draft_v1"):
			self.mod.preview_korea_payroll_closing_draft_apply_plan(draft=draft, actor="payroll-ops@example.com")

	def test_preview_api_preserves_no_submit_approve_send_provider_boundary(self):
		plan = self.mod.preview_korea_payroll_closing_draft_apply_plan(draft=draft_payload(), actor="payroll-ops@example.com")

		self.assertEqual(plan["runtime_action"], "preview_only")
		self.assertFalse(plan.get("saved", False))
		self.assertFalse(plan.get("submitted", False))
		self.assertFalse(plan.get("approved", False))
		self.assertFalse(plan.get("sent", False))
		self.assertFalse(plan.get("provider_called", False))


if __name__ == "__main__":
	unittest.main()
