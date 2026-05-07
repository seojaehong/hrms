#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import json
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "payroll_closing_draft_apply.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_payroll_closing_draft_apply", MODULE_PATH)
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


class TestKoreaPayrollClosingDraftApply(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()

	def test_builds_runtime_draft_apply_plan_without_mutating_or_saving(self):
		draft = draft_payload()
		original = copy.deepcopy(draft)

		plan = self.mod.build_korea_payroll_closing_draft_apply_plan(draft, actor="payroll-ops@example.com")

		self.assertEqual(plan["contract_type"], "korea_payroll_closing_draft_apply_plan_v1")
		self.assertEqual(plan["source_draft_contract_type"], "korea_payroll_closing_draft_v1")
		self.assertEqual(plan["runtime_action"], "preview_runtime_draft_apply")
		self.assertTrue(plan["requires_runtime_apply"])
		self.assertEqual(plan["mutation_boundary"], "draft_only_no_submit_no_approve_no_send")
		self.assertEqual(plan["would_create_doctype"], "Korea Payroll Closing Draft")
		self.assertEqual(plan["docstatus"], 0)
		self.assertEqual(plan["status"], "draft_pending_human_approval")
		self.assertEqual(plan["actor"], "payroll-ops@example.com")
		self.assertEqual(plan["company"], "Korea Demo Co")
		self.assertEqual(plan["workplace"], "Seoul HQ")
		self.assertEqual(plan["field_values"]["source_payroll_entry"], "PAY-ENTRY-0001")
		self.assertEqual(plan["field_values"]["payload"]["review_checklist"][0]["key"], "attendance_reviewed")
		self.assertEqual(plan["field_values"]["audit_preview"]["runtime_action"], "preview_only")
		self.assertTrue(plan["requires_human_approval"])
		self.assertEqual(plan["ai_role"], "assistant_only")
		self.assertEqual(draft, original)
		self.assertFalse(self._contains_forbidden_numeric_score(plan))

	def test_builds_json_safe_doctype_insert_preview_for_runtime_adapter(self):
		plan = self.mod.build_korea_payroll_closing_draft_apply_plan(
			draft_payload(), actor="payroll-ops@example.com"
		)

		insert_preview = plan["doctype_insert_preview"]
		fields = insert_preview["fields"]

		self.assertEqual(insert_preview["doctype"], "Korea Payroll Closing Draft")
		self.assertEqual(insert_preview["runtime_action"], "preview_only")
		self.assertTrue(insert_preview["requires_runtime_apply"])
		self.assertEqual(insert_preview["mutation_boundary"], "draft_only_no_submit_no_approve_no_send")
		self.assertEqual(fields["docstatus"], 0)
		self.assertEqual(fields["company"], "Korea Demo Co")
		self.assertEqual(fields["workplace"], "Seoul HQ")
		self.assertEqual(fields["source_payroll_entry"], "PAY-ENTRY-0001")
		self.assertIsInstance(fields["payload"], str)
		self.assertIsInstance(fields["audit_preview"], str)
		self.assertEqual(json.loads(fields["payload"])["review_checklist"][0]["key"], "attendance_reviewed")
		self.assertEqual(json.loads(fields["audit_preview"])["runtime_action"], "preview_only")
		for forbidden in ["name", "owner", "submitted", "submit", "send", "approve"]:
			self.assertNotIn(forbidden, fields)

	def test_rejects_preview_api_drafts_instead_of_runtime_draft_contract(self):
		draft = draft_payload()
		draft["contract_type"] = "korea_payroll_closing_draft_preview_v1"

		with self.assertRaisesRegex(ValueError, "draft.contract_type must be korea_payroll_closing_draft_v1"):
			self.mod.build_korea_payroll_closing_draft_apply_plan(draft, actor="payroll-ops@example.com")

	def test_rejects_unsafe_mutation_boundaries_before_runtime_apply(self):
		for field, value, message in [
			("runtime_action", "submit", "draft.runtime_action must be create_draft"),
			("requires_runtime_apply", False, "draft.requires_runtime_apply must be true"),
			("mutation_boundary", "submit_and_send", "draft.mutation_boundary must be draft_only_no_submit_no_approve_no_send"),
			("doctype", "Salary Slip", "draft.doctype must be Korea Payroll Closing Draft"),
			("status", "submitted", "draft.status must be draft_pending_human_approval"),
			("requires_human_approval", False, "draft.requires_human_approval must be true"),
			("ai_role", "autonomous_agent", "draft.ai_role must be assistant_only"),
		]:
			draft = draft_payload()
			draft[field] = value
			with self.subTest(field=field):
				with self.assertRaisesRegex(ValueError, message):
					self.mod.build_korea_payroll_closing_draft_apply_plan(draft, actor="payroll-ops@example.com")

	def test_rejects_unchecked_review_checklist_and_scope_mismatch(self):
		draft = draft_payload()
		draft["payload"]["review_checklist"][0]["checked"] = "true"
		with self.assertRaisesRegex(ValueError, "draft.payload.review_checklist.checked must be a boolean true"):
			self.mod.build_korea_payroll_closing_draft_apply_plan(draft, actor="payroll-ops@example.com")

		draft = draft_payload()
		draft["payload"]["session"]["company"] = "Other Co"
		with self.assertRaisesRegex(ValueError, "draft.payload.session.company must match draft.company"):
			self.mod.build_korea_payroll_closing_draft_apply_plan(draft, actor="payroll-ops@example.com")

	def test_rejects_spoofed_source_session_contract_type(self):
		draft = draft_payload()
		draft["source_session_contract_type"] = "custom_session_v1"
		with self.assertRaisesRegex(ValueError, "draft.source_session_contract_type must be korea_payroll_closing_session_v1"):
			self.mod.build_korea_payroll_closing_draft_apply_plan(draft, actor="payroll-ops@example.com")

		draft = draft_payload()
		draft["payload"]["session"]["contract_type"] = "custom_session_v1"
		with self.assertRaisesRegex(ValueError, "draft.payload.session.contract_type must be korea_payroll_closing_session_v1"):
			self.mod.build_korea_payroll_closing_draft_apply_plan(draft, actor="payroll-ops@example.com")

	def test_rejects_invalid_or_reversed_periods_at_apply_boundary(self):
		for period_start, period_end, message in [
			("not-a-date", "2026-05-31", "draft.period_start must be an ISO date"),
			("2026-06-01", "2026-05-31", "draft.period_start must be on or before draft.period_end"),
		]:
			draft = draft_payload()
			draft["period_start"] = period_start
			draft["period_end"] = period_end
			draft["payload"]["session"]["period_start"] = period_start
			draft["payload"]["session"]["period_end"] = period_end
			with self.subTest(period_start=period_start, period_end=period_end):
				with self.assertRaisesRegex(ValueError, message):
					self.mod.build_korea_payroll_closing_draft_apply_plan(draft, actor="payroll-ops@example.com")

	def test_rejects_forbidden_numeric_score_fields_before_payload_copy(self):
		for key in ["risk_score", "successRate", "probability-score"]:
			draft = draft_payload()
			draft["payload"]["payroll_artifacts"][key] = 0.75
			with self.subTest(key=key):
				with self.assertRaisesRegex(ValueError, f"{key} is not allowed in payroll closing draft apply payloads"):
					self.mod.build_korea_payroll_closing_draft_apply_plan(draft, actor="payroll-ops@example.com")

	def test_actor_must_be_actual_non_empty_string(self):
		for actor in [None, 123, "   "]:
			with self.subTest(actor=actor):
				with self.assertRaisesRegex(ValueError, "actor must be a non-empty string"):
					self.mod.build_korea_payroll_closing_draft_apply_plan(draft_payload(), actor=actor)

	def _contains_forbidden_numeric_score(self, value):
		if isinstance(value, dict):
			for key, nested in value.items():
				if key in {"risk_score", "probability", "success_rate", "legal_risk_score"}:
					return True
				if self._contains_forbidden_numeric_score(nested):
					return True
		if isinstance(value, list):
			return any(self._contains_forbidden_numeric_score(item) for item in value)
		return False


if __name__ == "__main__":
	unittest.main()
