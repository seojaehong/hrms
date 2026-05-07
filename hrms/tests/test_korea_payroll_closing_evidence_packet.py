#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "payroll_closing_evidence_packet.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_payroll_closing_evidence_packet", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


def blocked_session():
	return {
		"contract_type": "korea_payroll_closing_session_v1",
		"company": "Korea Demo Co",
		"workplace": "Seoul HQ",
		"period_start": "2026-05-01",
		"period_end": "2026-05-31",
		"status": "blocked",
		"blockers": [
			{"code": "attendance_not_ready", "severity": "blocking", "message": "Attendance must be reviewed."},
			{"code": "approver_missing", "severity": "blocking", "message": "Approver must be assigned."},
		],
		"next_actions": [
			{"action": "review_attendance", "label": "Review attendance", "enabled": True, "requires_runtime_apply": False},
			{"action": "assign_payroll_approver", "label": "Assign approver", "enabled": True, "requires_runtime_apply": True},
		],
		"readiness_cards": [
			{"key": "attendance", "status": "blocked", "label": "Attendance"},
			{"key": "payroll", "status": "ready", "label": "Payroll"},
		],
		"payroll_artifacts": {
			"payroll_entry": "PAY-ENTRY-0001",
			"salary_slip_count": 2,
			"statutory_totals": {"gross_earnings": 5250000, "total_employee_deductions": 420000},
		},
		"approval_state": {"approver": None, "status": "approver_missing"},
		"notification_state": {"payslip_artifacts_ready": True, "kakao_queue_ready": True, "recipient_count": 2},
		"expense_state": {"settlement_ready": False, "open_claim_count": 1, "approved_unpaid_count": 0},
		"contract_state": {"ready": False, "missing_contract_count": 1, "stale_contract_count": 0},
		"audit_preview": {
			"event_type": "korea_payroll_closing_session_review_v1",
			"runtime_action": "preview_only",
			"requires_runtime_apply": True,
			"company": "Korea Demo Co",
			"workplace": "Seoul HQ",
			"period_start": "2026-05-01",
			"period_end": "2026-05-31",
			"status": "blocked",
			"blocker_codes": ["attendance_not_ready", "approver_missing"],
		},
		"requires_human_approval": True,
		"ai_role": "assistant_only",
	}


class TestKoreaPayrollClosingEvidencePacket(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()

	def test_builds_human_review_evidence_packet_from_session(self):
		session = blocked_session()
		original = copy.deepcopy(session)

		packet = self.mod.build_korea_payroll_closing_evidence_packet(
			session,
			actor="hr-ops@example.com",
			purpose="monthly payroll close review",
		)

		self.assertEqual(packet["contract_type"], "korea_payroll_closing_evidence_packet_v1")
		self.assertEqual(packet["source_session_contract_type"], "korea_payroll_closing_session_v1")
		self.assertEqual(packet["runtime_action"], "preview_only")
		self.assertFalse(packet["requires_runtime_apply"])
		self.assertEqual(packet["company"], "Korea Demo Co")
		self.assertEqual(packet["workplace"], "Seoul HQ")
		self.assertEqual(packet["period_start"], "2026-05-01")
		self.assertEqual(packet["period_end"], "2026-05-31")
		self.assertEqual(packet["status"], "blocked")
		self.assertEqual(packet["actor"], "hr-ops@example.com")
		self.assertEqual(packet["purpose"], "monthly payroll close review")
		self.assertTrue(packet["requires_human_approval"])
		self.assertEqual(packet["ai_role"], "assistant_only")
		self.assertEqual(packet["blocker_codes"], ["attendance_not_ready", "approver_missing"])
		self.assertEqual(
			[item["key"] for item in packet["evidence_items"]],
			["attendance", "payroll_artifacts", "approval", "notification", "expense_settlement", "employment_contracts", "audit_preview"],
		)
		self.assertEqual(packet["evidence_items"][1]["summary"]["payroll_entry"], "PAY-ENTRY-0001")
		self.assertEqual(packet["evidence_items"][4]["summary"]["open_claim_count"], 1)
		self.assertEqual(packet["evidence_items"][5]["summary"]["missing_contract_count"], 1)
		self.assertEqual(packet["review_checklist"][0]["blocker_code"], "attendance_not_ready")
		self.assertEqual(packet["review_checklist"][0]["status"], "needs_human_review")
		self.assertEqual(packet["next_actions"][0]["action"], "review_attendance")
		self.assertEqual(packet["source_session"], original)
		self.assertEqual(session, original)
		self.assertFalse(self._contains_forbidden_numeric_score(packet))

	def test_review_ready_session_gets_final_human_approval_checklist_item(self):
		session = blocked_session()
		session["status"] = "review_ready"
		session["blockers"] = []
		session["audit_preview"]["status"] = "review_ready"
		session["audit_preview"]["blocker_codes"] = []

		packet = self.mod.build_korea_payroll_closing_evidence_packet(session, actor="hr-ops@example.com")

		self.assertEqual(packet["blocker_codes"], [])
		self.assertEqual(packet["review_checklist"], [{"status": "needs_human_approval", "action": "record_human_review", "requires_runtime_apply": True}])

	def test_rejects_malformed_session_and_autonomous_ai_role(self):
		for field, value, message in [
			("contract_type", "bad", "session.contract_type must be korea_payroll_closing_session_v1"),
			("requires_human_approval", False, "session.requires_human_approval must be true"),
			("ai_role", "autonomous_agent", "session.ai_role must be assistant_only"),
			("blockers", "attendance_not_ready", "session.blockers must be a list"),
			("next_actions", {}, "session.next_actions must be a list"),
		]:
			session = blocked_session()
			session[field] = value
			with self.subTest(field=field):
				with self.assertRaisesRegex(ValueError, message):
					self.mod.build_korea_payroll_closing_evidence_packet(session, actor="hr-ops@example.com")

	def test_rejects_audit_preview_scope_mismatch_and_score_fields(self):
		session = blocked_session()
		session["audit_preview"]["company"] = "Other Co"
		with self.assertRaisesRegex(ValueError, "session.audit_preview.company must match session.company"):
			self.mod.build_korea_payroll_closing_evidence_packet(session, actor="hr-ops@example.com")

		for key in ["legal_risk_score", "risk score", "Success Rate", "probability score"]:
			session = blocked_session()
			session["payroll_artifacts"][key] = 0.8
			with self.subTest(key=key):
				with self.assertRaisesRegex(ValueError, f"{key} is not allowed in payroll closing evidence packets"):
					self.mod.build_korea_payroll_closing_evidence_packet(session, actor="hr-ops@example.com")

	def test_rejects_unsafe_or_malformed_next_actions(self):
		for action, message in [
			({"action": "submit_payroll", "label": "Submit now"}, "session.next_actions\[0\].action is not allowed"),
			({"action": "review_attendance", "requires_runtime_apply": "false"}, "session.next_actions\[0\].requires_runtime_apply must be a bool"),
			("review_attendance", "session.next_actions\[0\] must be a dict"),
		]:
			session = blocked_session()
			session["next_actions"] = [action]
			with self.subTest(action=action):
				with self.assertRaisesRegex(ValueError, message):
					self.mod.build_korea_payroll_closing_evidence_packet(session, actor="hr-ops@example.com")

	def test_actor_and_purpose_must_be_plain_text(self):
		for actor in [None, 123, "   "]:
			with self.subTest(actor=actor):
				with self.assertRaisesRegex(ValueError, "actor must be a non-empty string"):
					self.mod.build_korea_payroll_closing_evidence_packet(blocked_session(), actor=actor)
		with self.assertRaisesRegex(ValueError, "purpose must be a non-empty string"):
			self.mod.build_korea_payroll_closing_evidence_packet(blocked_session(), actor="hr-ops@example.com", purpose=" ")

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
