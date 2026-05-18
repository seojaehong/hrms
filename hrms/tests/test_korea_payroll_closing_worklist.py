#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "payroll_closing_worklist.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_payroll_closing_worklist", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


class TestKoreaPayrollClosingWorklist(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()
		self.blocked_session = {
			"contract_type": "korea_payroll_closing_session_v1",
			"name": "KPCS-2026-05-SEOUL",
			"company": "Korea Demo Co",
			"workplace": "Seoul HQ",
			"period_start": "2026-05-01",
			"period_end": "2026-05-31",
			"status": "blocked",
			"blockers": [
				{"code": "attendance_not_ready", "severity": "blocking", "message": "Attendance review required"},
				{"code": "approver_missing", "severity": "blocking", "message": "Approver required"},
			],
			"next_actions": [
				{"action": "resolve_attendance_blockers", "label": "Resolve attendance blockers", "requires_runtime_apply": True},
			],
			"readiness_cards": [],
			"payroll_artifacts": {"payroll_entry": "PAY-ENTRY-0001"},
			"approval_state": {"approver": None},
			"notification_state": {"payslip_artifacts_ready": True, "kakao_queue_ready": False},
			"audit_preview": {"runtime_action": "preview_only", "requires_runtime_apply": True},
			"requires_human_approval": True,
			"ai_role": "assistant_only",
		}
		self.ready_session = {
			"contract_type": "korea_payroll_closing_session_v1",
			"name": "KPCS-2026-05-BUSAN",
			"company": "Korea Demo Co",
			"workplace": "Busan Branch",
			"period_start": "2026-05-01",
			"period_end": "2026-05-31",
			"status": "review_ready",
			"blockers": [],
			"next_actions": [{"action": "review_payroll_artifacts", "label": "Review payroll artifacts", "requires_runtime_apply": False}],
			"readiness_cards": [],
			"payroll_artifacts": {"payroll_entry": "PAY-ENTRY-0002"},
			"approval_state": {"approver": "manager@example.com"},
			"notification_state": {"payslip_artifacts_ready": True, "kakao_queue_ready": True},
			"audit_preview": {"runtime_action": "preview_only", "requires_runtime_apply": True},
			"requires_human_approval": True,
			"ai_role": "assistant_only",
		}

	def test_builds_operator_worklist_from_payroll_closing_sessions(self):
		worklist = self.mod.build_korea_payroll_closing_worklist(
			sessions=[self.ready_session, self.blocked_session],
			company="Korea Demo Co",
			workplaces=["Seoul HQ", "Busan Branch"],
		)

		self.assertEqual(worklist["contract_type"], "korea_payroll_closing_worklist_v1")
		self.assertEqual(worklist["company"], "Korea Demo Co")
		self.assertEqual(worklist["workplaces"], ["Seoul HQ", "Busan Branch"])
		self.assertEqual(worklist["summary"], {"total_count": 2, "blocked_count": 1, "review_ready_count": 1})
		self.assertEqual([item["name"] for item in worklist["items"]], ["KPCS-2026-05-SEOUL", "KPCS-2026-05-BUSAN"])
		blocked_item = worklist["items"][0]
		self.assertEqual(blocked_item["status"], "blocked")
		self.assertEqual(blocked_item["blocker_codes"], ["attendance_not_ready", "approver_missing"])
		self.assertEqual(blocked_item["primary_action"]["action"], "resolve_attendance_blockers")
		self.assertFalse(blocked_item["primary_action"]["requires_runtime_apply"])
		self.assertEqual(blocked_item["route"], "korea-payroll-closing-session/KPCS-2026-05-SEOUL")
		self.assertEqual(worklist["runtime_action"], "preview_only")
		self.assertFalse(worklist["requires_runtime_apply"])
		self.assertTrue(worklist["requires_human_approval"])
		self.assertEqual(worklist["ai_role"], "assistant_only")
		self.assertFalse(self._contains_forbidden_numeric_score(worklist))

	def test_filters_to_actor_workplaces_without_mutating_sessions(self):
		original_name = self.ready_session["name"]
		worklist = self.mod.build_korea_payroll_closing_worklist(
			sessions=[self.blocked_session, self.ready_session],
			company="Korea Demo Co",
			workplaces=["Busan Branch"],
		)

		self.assertEqual(worklist["summary"], {"total_count": 1, "blocked_count": 0, "review_ready_count": 1})
		self.assertEqual([item["workplace"] for item in worklist["items"]], ["Busan Branch"])
		worklist["items"][0]["name"] = "MUTATED"
		self.assertEqual(self.ready_session["name"], original_name)

	def test_cross_company_or_malformed_session_fails_closed(self):
		bad_company = dict(self.blocked_session, company="Other Co")
		with self.assertRaisesRegex(ValueError, "session.company must match worklist company"):
			self.mod.build_korea_payroll_closing_worklist(sessions=[bad_company], company="Korea Demo Co", workplaces=["Seoul HQ"])

		bad_contract = dict(self.blocked_session, contract_type="wrong")
		with self.assertRaisesRegex(ValueError, "session.contract_type must be korea_payroll_closing_session_v1"):
			self.mod.build_korea_payroll_closing_worklist(sessions=[bad_contract], company="Korea Demo Co", workplaces=["Seoul HQ"])

		bad_approval = dict(self.blocked_session, requires_human_approval=False)
		with self.assertRaisesRegex(ValueError, "session.requires_human_approval must be true"):
			self.mod.build_korea_payroll_closing_worklist(sessions=[bad_approval], company="Korea Demo Co", workplaces=["Seoul HQ"])

	def test_route_segment_is_escaped_and_action_flags_are_route_only(self):
		session = dict(self.blocked_session, name="KPCS/../../Salary Slip/SECRET?x=1")
		session["next_actions"] = [{"action": "resolve_attendance_blockers", "label": "Resolve", "requires_runtime_apply": "false"}]

		worklist = self.mod.build_korea_payroll_closing_worklist(
			sessions=[session],
			company="Korea Demo Co",
			workplaces=["Seoul HQ"],
		)

		item = worklist["items"][0]
		self.assertEqual(item["name"], "KPCS/../../Salary Slip/SECRET?x=1")
		self.assertEqual(item["route"], "korea-payroll-closing-session/KPCS%2F..%2F..%2FSalary%20Slip%2FSECRET%3Fx%3D1")
		self.assertFalse(item["primary_action"]["requires_runtime_apply"])

	def test_rejects_malformed_inputs_and_unknown_statuses(self):
		with self.assertRaisesRegex(ValueError, "sessions must be a list"):
			self.mod.build_korea_payroll_closing_worklist(sessions={}, company="Korea Demo Co", workplaces=["Seoul HQ"])

		with self.assertRaisesRegex(ValueError, "workplaces must be a list of strings"):
			self.mod.build_korea_payroll_closing_worklist(sessions=[self.blocked_session], company="Korea Demo Co", workplaces="Seoul HQ")

		unknown_status = dict(self.blocked_session, status="approved")
		with self.assertRaisesRegex(ValueError, "session.status must be blocked or review_ready"):
			self.mod.build_korea_payroll_closing_worklist(sessions=[unknown_status], company="Korea Demo Co", workplaces=["Seoul HQ"])

	def _contains_forbidden_numeric_score(self, value):
		forbidden = {"risk_score", "probability", "success_rate", "score"}
		if isinstance(value, dict):
			for key, nested in value.items():
				if key in forbidden:
					return True
				if self._contains_forbidden_numeric_score(nested):
					return True
		if isinstance(value, list):
			return any(self._contains_forbidden_numeric_score(item) for item in value)
		return False


if __name__ == "__main__":
	unittest.main()
