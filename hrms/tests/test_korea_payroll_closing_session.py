#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "payroll_closing_session.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_payroll_closing_session", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


class TestKoreaPayrollClosingSession(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()

	def test_builds_review_ready_payroll_closing_session(self):
		session = self.mod.build_korea_payroll_closing_session(
			company="Korea Demo Co",
			workplace="Seoul HQ",
			period_start="2026-05-01",
			period_end="2026-05-31",
			attendance_summary={
				"company": "Korea Demo Co",
				"workplace": "Seoul HQ",
				"period_start": "2026-05-01",
				"period_end": "2026-05-31",
				"status": "ready",
				"employee_count": 2,
				"unmarked_days": [],
			},
			payroll_entry={
				"name": "PAY-ENTRY-0001",
				"company": "Korea Demo Co",
				"workplace": "Seoul HQ",
				"start_date": "2026-05-01",
				"end_date": "2026-05-31",
				"salary_slips": [
					{"name": "SAL-0001", "employee": "EMP-0001", "company": "Korea Demo Co", "workplace": "Seoul HQ", "status": "Submitted"},
					{"name": "SAL-0002", "employee": "EMP-0002", "company": "Korea Demo Co", "workplace": "Seoul HQ", "status": "Submitted"},
				],
				"statutory_batch_payload": {"totals": {"gross_earnings": 5250000, "total_employee_deductions": 420000}},
			},
			approval_state={"approver": "branch-manager@example.com", "status": "pending_review", "open_items": 1},
			notification_state={"payslip_artifacts_ready": True, "kakao_queue_ready": True, "recipient_count": 2},
		)

		self.assertEqual(session["contract_type"], "korea_payroll_closing_session_v1")
		self.assertEqual(session["company"], "Korea Demo Co")
		self.assertEqual(session["workplace"], "Seoul HQ")
		self.assertEqual(session["period_start"], "2026-05-01")
		self.assertEqual(session["period_end"], "2026-05-31")
		self.assertEqual(session["status"], "review_ready")
		self.assertEqual(session["blockers"], [])
		self.assertTrue(session["requires_human_approval"])
		self.assertEqual(session["ai_role"], "assistant_only")
		self.assertEqual(session["payroll_artifacts"]["payroll_entry"], "PAY-ENTRY-0001")
		self.assertEqual(session["payroll_artifacts"]["salary_slip_count"], 2)
		self.assertEqual(session["payroll_artifacts"]["statutory_totals"]["gross_earnings"], 5250000)
		self.assertEqual(session["approval_state"]["approver"], "branch-manager@example.com")
		self.assertEqual(session["notification_state"]["recipient_count"], 2)
		self.assertIn("review_payroll_artifacts", [action["action"] for action in session["next_actions"]])
		self.assertEqual(session["audit_preview"]["event_type"], "korea_payroll_closing_session_review_v1")
		self.assertFalse(self._contains_forbidden_numeric_score(session))

	def test_missing_attendance_creates_blocker(self):
		session = self.mod.build_korea_payroll_closing_session(
			company="Korea Demo Co",
			workplace="Seoul HQ",
			period_start="2026-05-01",
			period_end="2026-05-31",
			attendance_summary={"status": "blocked", "unmarked_days": ["2026-05-03"]},
			payroll_entry={"name": "PAY-ENTRY-0001", "company": "Korea Demo Co", "workplace": "Seoul HQ", "start_date": "2026-05-01", "end_date": "2026-05-31", "salary_slips": []},
			approval_state={"approver": "branch-manager@example.com"},
			notification_state={"payslip_artifacts_ready": True, "kakao_queue_ready": True},
		)

		self.assertEqual(session["status"], "blocked")
		self.assertIn("attendance_not_ready", [blocker["code"] for blocker in session["blockers"]])
		self.assertIn("resolve_attendance_blockers", [action["action"] for action in session["next_actions"]])

	def test_missing_approver_creates_blocker(self):
		session = self.mod.build_korea_payroll_closing_session(
			company="Korea Demo Co",
			workplace="Seoul HQ",
			period_start="2026-05-01",
			period_end="2026-05-31",
			attendance_summary={"status": "ready", "unmarked_days": []},
			payroll_entry={"name": "PAY-ENTRY-0001", "company": "Korea Demo Co", "workplace": "Seoul HQ", "start_date": "2026-05-01", "end_date": "2026-05-31", "salary_slips": []},
			approval_state={"status": "pending_review"},
			notification_state={"payslip_artifacts_ready": True, "kakao_queue_ready": True},
		)

		self.assertEqual(session["status"], "blocked")
		self.assertIn("approver_missing", [blocker["code"] for blocker in session["blockers"]])
		self.assertIn("assign_payroll_approver", [action["action"] for action in session["next_actions"]])

	def test_cross_company_or_workplace_payroll_data_fails_closed(self):
		with self.assertRaisesRegex(ValueError, "payroll_entry.company must match session company"):
			self.mod.build_korea_payroll_closing_session(
				company="Korea Demo Co",
				workplace="Seoul HQ",
				period_start="2026-05-01",
				period_end="2026-05-31",
				attendance_summary={"status": "ready"},
				payroll_entry={"name": "PAY-CROSS", "company": "Other Co", "workplace": "Seoul HQ", "start_date": "2026-05-01", "end_date": "2026-05-31"},
				approval_state={"approver": "branch-manager@example.com"},
				notification_state={},
			)

		with self.assertRaisesRegex(ValueError, "salary_slip.workplace must match session workplace"):
			self.mod.build_korea_payroll_closing_session(
				company="Korea Demo Co",
				workplace="Seoul HQ",
				period_start="2026-05-01",
				period_end="2026-05-31",
				attendance_summary={"status": "ready"},
				payroll_entry={
					"name": "PAY-WORKPLACE",
					"company": "Korea Demo Co",
					"workplace": "Seoul HQ",
					"start_date": "2026-05-01",
					"end_date": "2026-05-31",
					"salary_slips": [{"name": "SAL-BUSAN", "company": "Korea Demo Co", "workplace": "Busan Branch"}],
				},
				approval_state={"approver": "branch-manager@example.com"},
				notification_state={},
			)

		with self.assertRaisesRegex(ValueError, "approval_state.company must match session company"):
			self.mod.build_korea_payroll_closing_session(
				company="Korea Demo Co",
				workplace="Seoul HQ",
				period_start="2026-05-01",
				period_end="2026-05-31",
				attendance_summary={"status": "ready"},
				payroll_entry={"name": "PAY-ENTRY", "company": "Korea Demo Co", "workplace": "Seoul HQ", "start_date": "2026-05-01", "end_date": "2026-05-31", "salary_slips": []},
				approval_state={"company": "Other Co", "approver": "branch-manager@example.com"},
				notification_state={},
			)

		with self.assertRaisesRegex(ValueError, "notification_state.workplace must match session workplace"):
			self.mod.build_korea_payroll_closing_session(
				company="Korea Demo Co",
				workplace="Seoul HQ",
				period_start="2026-05-01",
				period_end="2026-05-31",
				attendance_summary={"status": "ready"},
				payroll_entry={"name": "PAY-ENTRY", "company": "Korea Demo Co", "workplace": "Seoul HQ", "start_date": "2026-05-01", "end_date": "2026-05-31", "salary_slips": []},
				approval_state={"approver": "branch-manager@example.com"},
				notification_state={"company": "Korea Demo Co", "workplace": "Busan Branch"},
			)

	def test_missing_statutory_or_kakao_artifacts_create_blockers(self):
		session = self.mod.build_korea_payroll_closing_session(
			company="Korea Demo Co",
			workplace="Seoul HQ",
			period_start="2026-05-01",
			period_end="2026-05-31",
			attendance_summary={"status": "ready", "unmarked_days": []},
			payroll_entry={"name": "PAY-ENTRY-0001", "company": "Korea Demo Co", "workplace": "Seoul HQ", "start_date": "2026-05-01", "end_date": "2026-05-31", "salary_slips": [{"name": "SAL-0001", "company": "Korea Demo Co", "workplace": "Seoul HQ"}]},
			approval_state={"approver": "branch-manager@example.com"},
			notification_state={"payslip_artifacts_ready": True, "kakao_queue_ready": False},
		)

		self.assertEqual(session["status"], "blocked")
		self.assertIn("statutory_artifacts_missing", [blocker["code"] for blocker in session["blockers"]])
		self.assertIn("kakao_queue_not_ready", [blocker["code"] for blocker in session["blockers"]])
		self.assertIn("prepare_statutory_artifacts", [action["action"] for action in session["next_actions"]])
		self.assertIn("prepare_kakao_queue", [action["action"] for action in session["next_actions"]])

	def test_salary_slip_period_mismatch_fails_closed(self):
		with self.assertRaisesRegex(ValueError, "salary_slip.period_end must match session period_end"):
			self.mod.build_korea_payroll_closing_session(
				company="Korea Demo Co",
				workplace="Seoul HQ",
				period_start="2026-05-01",
				period_end="2026-05-31",
				attendance_summary={"status": "ready"},
				payroll_entry={
					"name": "PAY-PERIOD",
					"company": "Korea Demo Co",
					"workplace": "Seoul HQ",
					"start_date": "2026-05-01",
					"end_date": "2026-05-31",
					"salary_slips": [{"name": "SAL-JUNE", "company": "Korea Demo Co", "workplace": "Seoul HQ", "start_date": "2026-05-01", "end_date": "2026-06-30"}],
				},
				approval_state={"approver": "branch-manager@example.com"},
				notification_state={},
			)

	def test_invalid_period_fails_closed(self):
		with self.assertRaisesRegex(ValueError, "period_start must be on or before period_end"):
			self.mod.build_korea_payroll_closing_session(
				company="Korea Demo Co",
				workplace="Seoul HQ",
				period_start="2026-06-01",
				period_end="2026-05-31",
				attendance_summary={},
				payroll_entry={},
				approval_state={},
				notification_state={},
			)

		with self.assertRaisesRegex(ValueError, "period_start must be an ISO date"):
			self.mod.build_korea_payroll_closing_session(
				company="Korea Demo Co",
				workplace="Seoul HQ",
				period_start="2026-05-01T09:00:00",
				period_end="2026-05-31",
				attendance_summary={},
				payroll_entry={},
				approval_state={},
				notification_state={},
			)

	def test_notification_readiness_rejects_string_boolean_values(self):
		with self.assertRaisesRegex(ValueError, "notification_state.payslip_artifacts_ready must be a boolean"):
			self.mod.build_korea_payroll_closing_session(
				company="Korea Demo Co",
				workplace="Seoul HQ",
				period_start="2026-05-01",
				period_end="2026-05-31",
				attendance_summary={"status": "ready", "unmarked_days": []},
				payroll_entry={
					"name": "PAY-ENTRY-0001",
					"company": "Korea Demo Co",
					"workplace": "Seoul HQ",
					"start_date": "2026-05-01",
					"end_date": "2026-05-31",
					"statutory_batch_payload": {"totals": {"gross_earnings": 5250000}},
				},
				approval_state={"approver": "branch-manager@example.com"},
				notification_state={"payslip_artifacts_ready": "false", "kakao_queue_ready": True},
			)

		with self.assertRaisesRegex(ValueError, "notification_state.kakao_queue_ready must be a boolean"):
			self.mod.build_korea_payroll_closing_session(
				company="Korea Demo Co",
				workplace="Seoul HQ",
				period_start="2026-05-01",
				period_end="2026-05-31",
				attendance_summary={"status": "ready", "unmarked_days": []},
				payroll_entry={
					"name": "PAY-ENTRY-0001",
					"company": "Korea Demo Co",
					"workplace": "Seoul HQ",
					"start_date": "2026-05-01",
					"end_date": "2026-05-31",
					"statutory_batch_payload": {"totals": {"gross_earnings": 5250000}},
				},
				approval_state={"approver": "branch-manager@example.com"},
				notification_state={"payslip_artifacts_ready": True, "kakao_queue_ready": "false"},
			)

	def test_top_level_payloads_must_be_dicts(self):
		with self.assertRaisesRegex(ValueError, "attendance_summary must be a dict"):
			self.mod.build_korea_payroll_closing_session(
				company="Korea Demo Co",
				workplace="Seoul HQ",
				period_start="2026-05-01",
				period_end="2026-05-31",
				attendance_summary=[],
				payroll_entry={},
				approval_state={},
				notification_state={},
			)

		with self.assertRaisesRegex(ValueError, "payroll_entry must be a dict"):
			self.mod.build_korea_payroll_closing_session(
				company="Korea Demo Co",
				workplace="Seoul HQ",
				period_start="2026-05-01",
				period_end="2026-05-31",
				attendance_summary={},
				payroll_entry="bad",
				approval_state={},
				notification_state={},
			)

	def _contains_forbidden_numeric_score(self, value):
		forbidden = {"risk_score", "score", "probability", "success_rate"}
		if isinstance(value, dict):
			return any(key in forbidden or self._contains_forbidden_numeric_score(child) for key, child in value.items())
		if isinstance(value, list):
			return any(self._contains_forbidden_numeric_score(child) for child in value)
		return False


if __name__ == "__main__":
	unittest.main()
