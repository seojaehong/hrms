#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "payroll_closing_draft.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_payroll_closing_draft", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


def review_ready_session():
	return {
		"contract_type": "korea_payroll_closing_session_v1",
		"company": "Korea Demo Co",
		"workplace": "Seoul HQ",
		"period_start": "2026-05-01",
		"period_end": "2026-05-31",
		"status": "review_ready",
		"blockers": [],
		"next_actions": [{"action": "request_human_approval", "enabled": True}],
		"readiness_cards": [{"key": "attendance", "status": "ready"}],
		"payroll_artifacts": {
			"payroll_entry": "PAY-ENTRY-0001",
			"salary_slip_count": 2,
			"statutory_totals": {"gross_earnings": 5250000, "total_employee_deductions": 420000},
		},
		"approval_state": {"approver": "branch-manager@example.com", "status": "pending_review"},
		"notification_state": {"payslip_artifacts_ready": True, "kakao_queue_ready": True, "recipient_count": 2},
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
		"requires_human_approval": True,
		"ai_role": "assistant_only",
	}


class TestKoreaPayrollClosingDraft(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()

	def test_builds_runtime_draft_payload_from_review_ready_session(self):
		session = review_ready_session()
		original = copy.deepcopy(session)

		draft = self.mod.build_korea_payroll_closing_draft(session, actor="hr-ops@example.com")

		self.assertEqual(draft["contract_type"], "korea_payroll_closing_draft_v1")
		self.assertEqual(draft["doctype"], "Korea Payroll Closing Draft")
		self.assertEqual(draft["runtime_action"], "create_draft")
		self.assertTrue(draft["requires_runtime_apply"])
		self.assertEqual(draft["company"], "Korea Demo Co")
		self.assertEqual(draft["workplace"], "Seoul HQ")
		self.assertEqual(draft["period_start"], "2026-05-01")
		self.assertEqual(draft["period_end"], "2026-05-31")
		self.assertEqual(draft["status"], "draft_pending_human_approval")
		self.assertEqual(draft["source_session_contract_type"], "korea_payroll_closing_session_v1")
		self.assertEqual(draft["source_payroll_entry"], "PAY-ENTRY-0001")
		self.assertEqual(draft["actor"], "hr-ops@example.com")
		self.assertTrue(draft["requires_human_approval"])
		self.assertEqual(draft["ai_role"], "assistant_only")
		self.assertEqual(draft["mutation_boundary"], "draft_only_no_submit_no_approve_no_send")
		self.assertEqual(draft["payload"]["payroll_artifacts"]["salary_slip_count"], 2)
		self.assertEqual(draft["payload"]["audit_preview"]["event_type"], "korea_payroll_closing_session_review_v1")
		self.assertEqual(session, original)
		self.assertFalse(self._contains_forbidden_numeric_score(draft))

	def test_blocked_session_cannot_create_runtime_draft(self):
		session = review_ready_session()
		session["status"] = "blocked"
		session["blockers"] = [{"code": "attendance_not_ready", "severity": "blocking"}]

		with self.assertRaisesRegex(ValueError, "session.status must be review_ready"):
			self.mod.build_korea_payroll_closing_draft(session, actor="hr-ops@example.com")

	def test_session_must_preserve_human_approval_and_assistant_only_role(self):
		for field, value, message in [
			("requires_human_approval", False, "session.requires_human_approval must be true"),
			("ai_role", "autonomous_agent", "session.ai_role must be assistant_only"),
		]:
			session = review_ready_session()
			session[field] = value
			with self.subTest(field=field):
				with self.assertRaisesRegex(ValueError, message):
					self.mod.build_korea_payroll_closing_draft(session, actor="hr-ops@example.com")

	def test_actor_must_be_actual_non_empty_string(self):
		for actor in [None, 123, "   "]:
			with self.subTest(actor=actor):
				with self.assertRaisesRegex(ValueError, "actor must be a non-empty string"):
					self.mod.build_korea_payroll_closing_draft(review_ready_session(), actor=actor)

	def test_rejects_missing_payroll_entry_before_draft_creation(self):
		session = review_ready_session()
		session["payroll_artifacts"] = {"salary_slip_count": 2, "statutory_totals": {"gross_earnings": 5250000}}

		with self.assertRaisesRegex(ValueError, "session.payroll_artifacts.payroll_entry is required"):
			self.mod.build_korea_payroll_closing_draft(session, actor="hr-ops@example.com")

	def test_rejects_forbidden_numeric_risk_score_fields_before_payload_copy(self):
		for key in [
			"legal_risk_score",
			"probability_score",
			"closing_success_rate",
			"riskScore",
			"risk-score",
			"Risk_Score",
			"successRate",
			"success-rate",
			"successrate",
			"probabilityScore",
			"Probability-Score",
		]:
			session = review_ready_session()
			session["payroll_artifacts"][key] = 0.91
			with self.subTest(key=key):
				with self.assertRaisesRegex(ValueError, f"{key} is not allowed in payroll closing draft payloads"):
					self.mod.build_korea_payroll_closing_draft(session, actor="hr-ops@example.com")

	def test_rejects_invalid_or_reversed_periods_at_draft_boundary(self):
		for period_start, period_end, message in [
			("not-a-date", "2026-05-31", "session.period_start must be an ISO date"),
			("2026-06-01", "2026-05-31", "session.period_start must be on or before session.period_end"),
		]:
			session = review_ready_session()
			session["period_start"] = period_start
			session["period_end"] = period_end
			with self.subTest(period_start=period_start, period_end=period_end):
				with self.assertRaisesRegex(ValueError, message):
					self.mod.build_korea_payroll_closing_draft(session, actor="hr-ops@example.com")

	def test_audit_preview_must_match_review_ready_session_scope(self):
		for field, value, message in [
			("runtime_action", "create_draft", "session.audit_preview.runtime_action must be preview_only"),
			("requires_runtime_apply", False, "session.audit_preview.requires_runtime_apply must be true"),
			("blocker_codes", ["attendance_not_ready"], "session.audit_preview.blocker_codes must be empty"),
			("company", "Other Co", "session.audit_preview.company must match session.company"),
		]:
			session = review_ready_session()
			session["audit_preview"][field] = value
			with self.subTest(field=field):
				with self.assertRaisesRegex(ValueError, message):
					self.mod.build_korea_payroll_closing_draft(session, actor="hr-ops@example.com")

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
