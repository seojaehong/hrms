#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import json
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "payroll_closing_evidence_packet_api.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_payroll_closing_evidence_packet_api", MODULE_PATH)
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
		],
		"next_actions": [
			{"action": "review_attendance", "label": "Review attendance", "enabled": True, "requires_runtime_apply": False},
		],
		"readiness_cards": [
			{"key": "attendance", "status": "blocked", "label": "Attendance"},
		],
		"payroll_artifacts": {
			"payroll_entry": "PAY-ENTRY-0001",
			"salary_slip_count": 2,
			"statutory_totals": {"gross_earnings": 5250000, "total_employee_deductions": 420000},
		},
		"approval_state": {"approver": None, "status": "approver_missing"},
		"notification_state": {"payslip_artifacts_ready": True, "kakao_queue_ready": True, "recipient_count": 2},
		"expense_state": {"settlement_ready": False, "open_claim_count": 1},
		"contract_state": {"ready": False, "missing_contract_count": 1},
		"audit_preview": {
			"event_type": "korea_payroll_closing_session_review_v1",
			"runtime_action": "preview_only",
			"requires_runtime_apply": True,
			"company": "Korea Demo Co",
			"workplace": "Seoul HQ",
			"period_start": "2026-05-01",
			"period_end": "2026-05-31",
			"status": "blocked",
			"blocker_codes": ["attendance_not_ready"],
		},
		"requires_human_approval": True,
		"ai_role": "assistant_only",
	}


class TestKoreaPayrollClosingEvidencePacketApi(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()

	def test_preview_api_builds_evidence_packet_from_json_session(self):
		packet = self.mod.preview_korea_payroll_closing_evidence_packet(
			session=json.dumps(blocked_session()),
			actor="hr-ops@example.com",
			purpose="monthly payroll close review",
		)

		self.assertEqual(packet["contract_type"], "korea_payroll_closing_evidence_packet_preview_v1")
		self.assertEqual(packet["evidence_packet_contract_type"], "korea_payroll_closing_evidence_packet_v1")
		self.assertEqual(packet["source_session_contract_type"], "korea_payroll_closing_session_v1")
		self.assertEqual(packet["runtime_action"], "preview_only")
		self.assertFalse(packet["requires_runtime_apply"])
		self.assertEqual(packet["actor"], "hr-ops@example.com")
		self.assertEqual(packet["purpose"], "monthly payroll close review")
		self.assertEqual(packet["blocker_codes"], ["attendance_not_ready"])
		self.assertTrue(packet["requires_human_approval"])
		self.assertEqual(packet["ai_role"], "assistant_only")
		self.assertEqual(packet["evidence_items"][1]["summary"]["payroll_entry"], "PAY-ENTRY-0001")

	def test_preview_api_defensively_copies_input_and_output(self):
		session = blocked_session()
		original = copy.deepcopy(session)

		packet = self.mod.preview_korea_payroll_closing_evidence_packet(session=session, actor="hr-ops@example.com")

		self.assertEqual(session, original)
		packet["source_session"]["payroll_artifacts"]["payroll_entry"] = "MUTATED"
		packet["evidence_items"][1]["summary"]["payroll_entry"] = "MUTATED"
		self.assertEqual(session["payroll_artifacts"]["payroll_entry"], "PAY-ENTRY-0001")

	def test_invalid_json_and_non_dict_session_are_rejected_before_delegation(self):
		with self.assertRaisesRegex(ValueError, "JSON payload is invalid"):
			self.mod.preview_korea_payroll_closing_evidence_packet(session='{"status":', actor="hr-ops@example.com")

		with self.assertRaisesRegex(ValueError, "session must be a dict or JSON object"):
			self.mod.preview_korea_payroll_closing_evidence_packet(session="[]", actor="hr-ops@example.com")

	def test_preview_api_preserves_core_fail_closed_validation(self):
		session = blocked_session()
		session["requires_human_approval"] = False

		with self.assertRaisesRegex(ValueError, "session.requires_human_approval must be true"):
			self.mod.preview_korea_payroll_closing_evidence_packet(session=session, actor="hr-ops@example.com")

	def test_preview_api_does_not_save_submit_approve_or_send(self):
		packet = self.mod.preview_korea_payroll_closing_evidence_packet(session=blocked_session(), actor="hr-ops@example.com")

		self.assertEqual(packet["runtime_action"], "preview_only")
		self.assertFalse(packet.get("saved", False))
		self.assertFalse(packet.get("submitted", False))
		self.assertFalse(packet.get("approved", False))
		self.assertFalse(packet.get("sent", False))
		self.assertFalse(packet.get("provider_called", False))


if __name__ == "__main__":
	unittest.main()
