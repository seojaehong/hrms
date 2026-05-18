#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "payroll_closing_draft_review.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_payroll_closing_draft_review", MODULE_PATH)
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


class TestKoreaPayrollClosingDraftReview(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()

	def test_builds_human_approval_review_action_preview(self):
		draft = runtime_draft()
		original = copy.deepcopy(draft)

		action = self.mod.build_korea_payroll_closing_draft_review_action(
			draft,
			actor="branch-manager@example.com",
			action="approve_draft",
			note="Reviewed attendance, statutory bases, notifications, and audit packet.",
		)

		self.assertEqual(action["contract_type"], "korea_payroll_closing_draft_review_action_v1")
		self.assertEqual(action["source_draft_contract_type"], "korea_payroll_closing_draft_runtime_insert_v1")
		self.assertEqual(action["runtime_action"], "preview_only")
		self.assertTrue(action["requires_runtime_apply"])
		self.assertEqual(action["mutation_boundary"], "human_review_only_no_submit_no_send_no_provider_call")
		self.assertEqual(action["would_update_doctype"], "Korea Payroll Closing Draft")
		self.assertEqual(action["would_update_name"], "KPCD-0001")
		self.assertEqual(action["would_set_status"], "draft_human_approved")
		self.assertEqual(action["action"], "approve_draft")
		self.assertEqual(action["actor"], "branch-manager@example.com")
		self.assertEqual(action["company"], "Korea Demo Co")
		self.assertEqual(action["workplace"], "Seoul HQ")
		self.assertEqual(action["period_start"], "2026-05-01")
		self.assertEqual(action["period_end"], "2026-05-31")
		self.assertTrue(action["requires_human_approval"])
		self.assertEqual(action["ai_role"], "assistant_only")
		self.assertEqual(action["audit_preview"]["event_type"], "korea_payroll_closing_draft_human_review_v1")
		self.assertEqual(action["audit_preview"]["runtime_action"], "preview_only")
		self.assertEqual(action["audit_preview"]["action"], "approve_draft")
		self.assertEqual(draft, original)
		self.assertFalse(self._contains_forbidden_numeric_score(action))

	def test_reject_and_request_changes_require_human_note(self):
		for action_name in ["reject_draft", "request_changes"]:
			with self.subTest(action=action_name):
				with self.assertRaisesRegex(ValueError, "note is required for reject_draft/request_changes"):
					self.mod.build_korea_payroll_closing_draft_review_action(
						runtime_draft(),
						actor="branch-manager@example.com",
						action=action_name,
						note="   ",
						)

	def test_only_assigned_approver_can_review_draft(self):
		with self.assertRaisesRegex(ValueError, "actor must match draft.approver"):
			self.mod.build_korea_payroll_closing_draft_review_action(
				runtime_draft(),
				actor="other-manager@example.com",
				action="approve_draft",
				note="Reviewed.",
			)

	def test_rejects_non_pending_or_unsafe_draft_contracts(self):
		for field, value, message in [
			("contract_type", "korea_payroll_closing_draft_review_action_v1", "draft.contract_type must be korea_payroll_closing_draft_runtime_insert_v1"),
			("status", "draft_human_approved", "draft.status must be draft_pending_human_approval"),
			("runtime_action", "preview_only", "draft.runtime_action must be runtime_draft_created"),
			("requires_human_approval", False, "draft.requires_human_approval must be true"),
			("ai_role", "autonomous_agent", "draft.ai_role must be assistant_only"),
		]:
			draft = runtime_draft()
			draft[field] = value
			with self.subTest(field=field):
				with self.assertRaisesRegex(ValueError, message):
					self.mod.build_korea_payroll_closing_draft_review_action(
						draft,
						actor="branch-manager@example.com",
						action="approve_draft",
						note="Reviewed.",
					)

	def test_rejects_invalid_action_actor_period_and_score_keys(self):
		for mutate, message in [
			(lambda d: d.update({"period_start": "not-a-date"}), "draft.period_start must be an ISO date"),
			(lambda d: d.update({"period_start": "2026-06-01"}), "draft.period_start must be on or before draft.period_end"),
			(lambda d: d.update({"legalRiskScoreCandidate": 0.9}), "legalRiskScoreCandidate is not allowed in payroll closing draft review payloads"),
		]:
			draft = runtime_draft()
			mutate(draft)
			with self.subTest(message=message):
				with self.assertRaisesRegex(ValueError, message):
					self.mod.build_korea_payroll_closing_draft_review_action(
						draft,
						actor="branch-manager@example.com",
						action="approve_draft",
						note="Reviewed.",
					)
		for actor in [None, 123, "   "]:
			with self.subTest(actor=actor):
				with self.assertRaisesRegex(ValueError, "actor must be a non-empty string"):
					self.mod.build_korea_payroll_closing_draft_review_action(
						runtime_draft(), actor=actor, action="approve_draft", note="Reviewed."
					)
		with self.assertRaisesRegex(ValueError, "action must be one of"):
			self.mod.build_korea_payroll_closing_draft_review_action(
				runtime_draft(), actor="branch-manager@example.com", action="submit", note="Reviewed."
			)

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
