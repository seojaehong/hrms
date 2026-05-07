#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import json
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "payroll_closing_draft_api.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_payroll_closing_draft_api", MODULE_PATH)
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


class TestKoreaPayrollClosingDraftApi(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()

	def test_preview_api_builds_draft_payload_from_json_session(self):
		session = review_ready_session()

		draft = self.mod.preview_korea_payroll_closing_draft(
			session=json.dumps(session),
			actor="hr-ops@example.com",
		)

		self.assertEqual(draft["contract_type"], "korea_payroll_closing_draft_preview_v1")
		self.assertEqual(draft["draft_contract_type"], "korea_payroll_closing_draft_v1")
		self.assertEqual(draft["runtime_action"], "preview_only")
		self.assertTrue(draft["requires_runtime_apply"])
		self.assertEqual(draft["would_create_doctype"], "Korea Payroll Closing Draft")
		self.assertEqual(draft["mutation_boundary"], "draft_only_no_submit_no_approve_no_send")
		self.assertEqual(draft["source_payroll_entry"], "PAY-ENTRY-0001")
		self.assertEqual(draft["actor"], "hr-ops@example.com")
		self.assertTrue(draft["requires_human_approval"])
		self.assertEqual(draft["ai_role"], "assistant_only")
		self.assertEqual(draft["payload"]["session"]["status"], "review_ready")

	def test_preview_api_does_not_mutate_caller_session_or_output_alias(self):
		session = review_ready_session()
		original = copy.deepcopy(session)

		draft = self.mod.preview_korea_payroll_closing_draft(session=session, actor="hr-ops@example.com")

		self.assertEqual(session, original)
		draft["payload"]["payroll_artifacts"]["payroll_entry"] = "MUTATED"
		self.assertEqual(session["payroll_artifacts"]["payroll_entry"], "PAY-ENTRY-0001")

	def test_invalid_json_and_non_dict_session_are_rejected_before_delegation(self):
		with self.assertRaisesRegex(ValueError, "JSON payload is invalid"):
			self.mod.preview_korea_payroll_closing_draft(session='{"status":', actor="hr-ops@example.com")

		with self.assertRaisesRegex(ValueError, "session must be a dict or JSON object"):
			self.mod.preview_korea_payroll_closing_draft(session="[]", actor="hr-ops@example.com")

	def test_preview_api_preserves_draft_boundary_fail_closed_validation(self):
		session = review_ready_session()
		session["status"] = "blocked"
		session["blockers"] = [{"code": "attendance_not_ready", "severity": "blocking"}]

		with self.assertRaisesRegex(ValueError, "session.status must be review_ready"):
			self.mod.preview_korea_payroll_closing_draft(session=session, actor="hr-ops@example.com")

	def test_preview_api_does_not_save_submit_approve_or_send(self):
		draft = self.mod.preview_korea_payroll_closing_draft(session=review_ready_session(), actor="hr-ops@example.com")

		self.assertEqual(draft["runtime_action"], "preview_only")
		self.assertFalse(draft.get("saved", False))
		self.assertFalse(draft.get("submitted", False))
		self.assertFalse(draft.get("approved", False))
		self.assertFalse(draft.get("sent", False))
		self.assertFalse(draft.get("provider_called", False))


if __name__ == "__main__":
	unittest.main()
