#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import json
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "payroll_closing_audit_event_api.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_payroll_closing_audit_event_api", MODULE_PATH)
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
		"blockers": [{"code": "attendance_not_ready", "severity": "blocking"}],
		"next_actions": [{"action": "review_blockers", "enabled": True}],
		"readiness_cards": [{"key": "attendance", "status": "blocked"}],
		"payroll_artifacts": {"payroll_entry": "PAY-ENTRY-0001"},
		"approval_state": {"approver": "branch-manager@example.com", "status": "pending_review"},
		"notification_state": {"payslip_artifacts_ready": True, "kakao_queue_ready": False},
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


class TestKoreaPayrollClosingAuditEventApi(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()

	def test_preview_api_builds_audit_event_from_json_session(self):
		event = self.mod.preview_korea_payroll_closing_audit_event(
			session=json.dumps(blocked_session()),
			actor="hr-ops@example.com",
			action="review_blockers",
			note="Attendance evidence reviewed by operator.",
		)

		self.assertEqual(event["contract_type"], "korea_payroll_closing_audit_event_preview_v1")
		self.assertEqual(event["audit_event_contract_type"], "korea_payroll_closing_audit_event_v1")
		self.assertEqual(event["source_session_contract_type"], "korea_payroll_closing_session_v1")
		self.assertEqual(event["runtime_action"], "preview_only")
		self.assertTrue(event["requires_runtime_apply"])
		self.assertTrue(event["requires_human_approval"])
		self.assertEqual(event["ai_role"], "assistant_only")
		self.assertEqual(event["actor"], "hr-ops@example.com")
		self.assertEqual(event["action"], "review_blockers")
		self.assertEqual(event["blocker_codes"], ["attendance_not_ready"])

	def test_preview_api_does_not_mutate_caller_session_or_output_alias(self):
		session = blocked_session()
		original = copy.deepcopy(session)

		event = self.mod.preview_korea_payroll_closing_audit_event(
			session=session,
			actor="hr-ops@example.com",
			action="review_blockers",
		)

		self.assertEqual(session, original)
		event["blocker_codes"].append("approver_missing")
		self.assertEqual(session["blockers"], [{"code": "attendance_not_ready", "severity": "blocking"}])

	def test_invalid_json_and_non_dict_session_are_rejected_before_delegation(self):
		with self.assertRaisesRegex(ValueError, "JSON payload is invalid"):
			self.mod.preview_korea_payroll_closing_audit_event(
				session='{"status":',
				actor="hr-ops@example.com",
				action="review_blockers",
			)

		with self.assertRaisesRegex(ValueError, "session must be a dict or JSON object"):
			self.mod.preview_korea_payroll_closing_audit_event(
				session="[]",
				actor="hr-ops@example.com",
				action="review_blockers",
			)

	def test_preview_api_preserves_strict_audit_validation(self):
		session = blocked_session()
		session["blockers"][0]["code"] = " attendance_not_ready"
		with self.assertRaisesRegex(ValueError, "session.blockers.code must be a known blocker code"):
			self.mod.preview_korea_payroll_closing_audit_event(
				session=session,
				actor="hr-ops@example.com",
				action="review_blockers",
			)

		with self.assertRaisesRegex(ValueError, "action must be one of"):
			self.mod.preview_korea_payroll_closing_audit_event(
				session=blocked_session(),
				actor="hr-ops@example.com",
				action="approve_payroll",
			)

	def test_preview_api_does_not_save_submit_approve_or_send(self):
		event = self.mod.preview_korea_payroll_closing_audit_event(
			session=blocked_session(),
			actor="hr-ops@example.com",
			action="review_blockers",
		)

		self.assertEqual(event["runtime_action"], "preview_only")
		self.assertFalse(event.get("saved", False))
		self.assertFalse(event.get("submitted", False))
		self.assertFalse(event.get("approved", False))
		self.assertFalse(event.get("sent", False))
		self.assertFalse(event.get("provider_called", False))


if __name__ == "__main__":
	unittest.main()
