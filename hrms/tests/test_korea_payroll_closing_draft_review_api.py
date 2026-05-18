#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import json
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "payroll_closing_draft_review_api.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_payroll_closing_draft_review_api", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


def runtime_draft():
	return {
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
		"source_payroll_entry": "PAY-ENTRY-0001",
		"approver": "branch-manager@example.com",
		"actor": "hr-ops@example.com",
		"docstatus": 0,
		"requires_human_approval": True,
		"ai_role": "assistant_only",
	}


class TestKoreaPayrollClosingDraftReviewApi(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()

	def test_preview_api_builds_review_action_from_json_runtime_draft(self):
		action = self.mod.preview_korea_payroll_closing_draft_review_action(
			draft=json.dumps(runtime_draft()),
			actor="branch-manager@example.com",
			action="approve_draft",
			note="Reviewed evidence packet and statutory basis rows.",
		)

		self.assertEqual(action["contract_type"], "korea_payroll_closing_draft_review_action_preview_v1")
		self.assertEqual(action["review_action_contract_type"], "korea_payroll_closing_draft_review_action_v1")
		self.assertEqual(action["source_draft_contract_type"], "korea_payroll_closing_draft_runtime_insert_v1")
		self.assertEqual(action["runtime_action"], "preview_only")
		self.assertTrue(action["requires_runtime_apply"])
		self.assertEqual(action["mutation_boundary"], "human_review_only_no_submit_no_send_no_provider_call")
		self.assertEqual(action["would_update_doctype"], "Korea Payroll Closing Draft")
		self.assertEqual(action["would_update_name"], "KPCD-0001")
		self.assertEqual(action["would_set_status"], "draft_human_approved")
		self.assertEqual(action["actor"], "branch-manager@example.com")
		self.assertTrue(action["requires_human_approval"])
		self.assertEqual(action["ai_role"], "assistant_only")

	def test_preview_api_does_not_mutate_caller_draft_or_alias_output(self):
		draft = runtime_draft()
		original = copy.deepcopy(draft)

		action = self.mod.preview_korea_payroll_closing_draft_review_action(
			draft=draft,
			actor="branch-manager@example.com",
			action="approve_draft",
			note="Reviewed.",
		)

		self.assertEqual(draft, original)
		action["source_draft"]["name"] = "MUTATED"
		self.assertEqual(draft["name"], "KPCD-0001")

	def test_invalid_json_and_non_dict_draft_are_rejected_before_delegation(self):
		with self.assertRaisesRegex(ValueError, "JSON payload is invalid"):
			self.mod.preview_korea_payroll_closing_draft_review_action(
				draft='{"contract_type":', actor="branch-manager@example.com", action="approve_draft", note="Reviewed."
			)

		with self.assertRaisesRegex(ValueError, "draft must be a dict or JSON object"):
			self.mod.preview_korea_payroll_closing_draft_review_action(
				draft="[]", actor="branch-manager@example.com", action="approve_draft", note="Reviewed."
			)

	def test_preview_api_rejects_preview_wrapper_instead_of_runtime_insert_contract(self):
		draft = runtime_draft()
		draft["contract_type"] = "korea_payroll_closing_draft_runtime_insert_api_v1"

		with self.assertRaisesRegex(ValueError, "draft.contract_type must be korea_payroll_closing_draft_runtime_insert_v1"):
			self.mod.preview_korea_payroll_closing_draft_review_action(
				draft=draft, actor="branch-manager@example.com", action="approve_draft", note="Reviewed."
			)

	def test_preview_api_preserves_no_submit_approve_send_provider_boundary(self):
		action = self.mod.preview_korea_payroll_closing_draft_review_action(
			draft=runtime_draft(), actor="branch-manager@example.com", action="approve_draft", note="Reviewed."
		)

		self.assertEqual(action["runtime_action"], "preview_only")
		self.assertFalse(action.get("saved", False))
		self.assertFalse(action.get("submitted", False))
		self.assertFalse(action.get("approved", False))
		self.assertFalse(action.get("sent", False))
		self.assertFalse(action.get("provider_called", False))


if __name__ == "__main__":
	unittest.main()
