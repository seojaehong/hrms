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
			approval_state={
				"company": "Korea Demo Co",
				"workplace": "Seoul HQ",
				"period_start": "2026-05-01",
				"period_end": "2026-05-31",
				"approver": "branch-manager@example.com",
				"status": "pending_review",
				"open_items": 1,
			},
			notification_state={
				"company": "Korea Demo Co",
				"workplace": "Seoul HQ",
				"period_start": "2026-05-01",
				"period_end": "2026-05-31",
				"payslip_artifacts_ready": True,
				"kakao_queue_ready": True,
				"recipient_count": 2,
			},
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

	def test_unsettled_expenses_create_closing_blocker_and_readiness_card(self):
		session = self.mod.build_korea_payroll_closing_session(
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
			notification_state={"payslip_artifacts_ready": True, "kakao_queue_ready": True},
			expense_state={
				"company": "Korea Demo Co",
				"workplace": "Seoul HQ",
				"period_start": "2026-05-01",
				"period_end": "2026-05-31",
				"settlement_ready": False,
				"open_claim_count": 3,
				"approved_unpaid_count": 1,
			},
		)

		self.assertEqual(session["status"], "blocked")
		self.assertIn("expense_settlement_not_ready", [blocker["code"] for blocker in session["blockers"]])
		self.assertIn("resolve_expense_settlements", [action["action"] for action in session["next_actions"]])
		expense_card = next(card for card in session["readiness_cards"] if card["key"] == "expense_settlements")
		self.assertEqual(expense_card["state"], "blocked")
		self.assertEqual(expense_card["summary"], {"open_claim_count": 3, "approved_unpaid_count": 1})
		self.assertEqual(session["expense_state"]["requires_runtime_apply"], False)

	def test_contract_state_creates_blocker_and_readiness_card_when_missing_artifacts(self):
		session = self.mod.build_korea_payroll_closing_session(
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
			notification_state={"payslip_artifacts_ready": True, "kakao_queue_ready": True},
			contract_state={
				"company": "Korea Demo Co",
				"workplace": "Seoul HQ",
				"period_start": "2026-05-01",
				"period_end": "2026-05-31",
				"contracts_reviewed": False,
				"missing_contract_count": 2,
				"stale_contract_count": 1,
			},
		)

		self.assertEqual(session["status"], "blocked")
		self.assertIn("employment_contracts_not_ready", [blocker["code"] for blocker in session["blockers"]])
		self.assertIn("review_employment_contracts", [action["action"] for action in session["next_actions"]])
		contract_card = next(card for card in session["readiness_cards"] if card["key"] == "employment_contracts")
		self.assertEqual(contract_card["state"], "blocked")
		self.assertEqual(contract_card["summary"], {"missing_contract_count": 2, "stale_contract_count": 1})
		self.assertEqual(session["contract_state"]["requires_runtime_apply"], False)

	def test_contract_state_conflicting_counts_fail_closed_when_marked_reviewed(self):
		session = self.mod.build_korea_payroll_closing_session(
			company="Korea Demo Co",
			workplace="Seoul HQ",
			period_start="2026-05-01",
			period_end="2026-05-31",
			attendance_summary={"status": "ready", "unmarked_days": []},
			payroll_entry={"name": "PAY-ENTRY-0001", "company": "Korea Demo Co", "workplace": "Seoul HQ", "start_date": "2026-05-01", "end_date": "2026-05-31", "statutory_batch_payload": {"totals": {"gross_earnings": 5250000}}},
			approval_state={"approver": "branch-manager@example.com"},
			notification_state={"payslip_artifacts_ready": True, "kakao_queue_ready": True},
			contract_state={"contracts_reviewed": True, "missing_contract_count": 1, "stale_contract_count": 0},
		)

		self.assertEqual(session["status"], "blocked")
		self.assertIn("employment_contracts_not_ready", [blocker["code"] for blocker in session["blockers"]])
		contract_card = next(card for card in session["readiness_cards"] if card["key"] == "employment_contracts")
		self.assertEqual(contract_card["state"], "blocked")

	def test_contract_state_scope_and_boolean_validation_fail_closed(self):
		with self.assertRaisesRegex(ValueError, "contract_state.workplace must match session workplace"):
			self.mod.build_korea_payroll_closing_session(
				company="Korea Demo Co",
				workplace="Seoul HQ",
				period_start="2026-05-01",
				period_end="2026-05-31",
				attendance_summary={"status": "ready", "unmarked_days": []},
				payroll_entry={"name": "PAY-ENTRY-0001", "company": "Korea Demo Co", "workplace": "Seoul HQ", "start_date": "2026-05-01", "end_date": "2026-05-31", "statutory_batch_payload": {"totals": {"gross_earnings": 5250000}}},
				approval_state={"approver": "branch-manager@example.com"},
				notification_state={"payslip_artifacts_ready": True, "kakao_queue_ready": True},
				contract_state={"company": "Korea Demo Co", "workplace": "Busan Branch", "contracts_reviewed": True},
			)

		with self.assertRaisesRegex(ValueError, "contract_state.contracts_reviewed must be a boolean"):
			self.mod.build_korea_payroll_closing_session(
				company="Korea Demo Co",
				workplace="Seoul HQ",
				period_start="2026-05-01",
				period_end="2026-05-31",
				attendance_summary={"status": "ready", "unmarked_days": []},
				payroll_entry={"name": "PAY-ENTRY-0001", "company": "Korea Demo Co", "workplace": "Seoul HQ", "start_date": "2026-05-01", "end_date": "2026-05-31", "statutory_batch_payload": {"totals": {"gross_earnings": 5250000}}},
				approval_state={"approver": "branch-manager@example.com"},
				notification_state={"payslip_artifacts_ready": True, "kakao_queue_ready": True},
				contract_state={"contracts_reviewed": "true"},
			)

	def test_expense_state_scope_and_boolean_validation_fail_closed(self):
		with self.assertRaisesRegex(ValueError, "expense_state.workplace must match session workplace"):
			self.mod.build_korea_payroll_closing_session(
				company="Korea Demo Co",
				workplace="Seoul HQ",
				period_start="2026-05-01",
				period_end="2026-05-31",
				attendance_summary={"status": "ready", "unmarked_days": []},
				payroll_entry={"name": "PAY-ENTRY-0001", "company": "Korea Demo Co", "workplace": "Seoul HQ", "start_date": "2026-05-01", "end_date": "2026-05-31", "statutory_batch_payload": {"totals": {"gross_earnings": 5250000}}},
				approval_state={"approver": "branch-manager@example.com"},
				notification_state={"payslip_artifacts_ready": True, "kakao_queue_ready": True},
				expense_state={"company": "Korea Demo Co", "workplace": "Busan Branch", "settlement_ready": True},
			)

		with self.assertRaisesRegex(ValueError, "expense_state.settlement_ready must be a boolean"):
			self.mod.build_korea_payroll_closing_session(
				company="Korea Demo Co",
				workplace="Seoul HQ",
				period_start="2026-05-01",
				period_end="2026-05-31",
				attendance_summary={"status": "ready", "unmarked_days": []},
				payroll_entry={"name": "PAY-ENTRY-0001", "company": "Korea Demo Co", "workplace": "Seoul HQ", "start_date": "2026-05-01", "end_date": "2026-05-31", "statutory_batch_payload": {"totals": {"gross_earnings": 5250000}}},
				approval_state={"approver": "branch-manager@example.com"},
				notification_state={"payslip_artifacts_ready": True, "kakao_queue_ready": True},
				expense_state={"settlement_ready": "false"},
			)

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

	def test_ready_source_artifacts_require_explicit_scope_and_period(self):
		base_kwargs = {
			"company": "Korea Demo Co",
			"workplace": "Seoul HQ",
			"period_start": "2026-05-01",
			"period_end": "2026-05-31",
			"attendance_summary": {
				"company": "Korea Demo Co",
				"workplace": "Seoul HQ",
				"period_start": "2026-05-01",
				"period_end": "2026-05-31",
				"status": "ready",
				"unmarked_days": [],
			},
			"payroll_entry": {
				"name": "PAY-ENTRY-0001",
				"company": "Korea Demo Co",
				"workplace": "Seoul HQ",
				"start_date": "2026-05-01",
				"end_date": "2026-05-31",
				"statutory_batch_payload": {"totals": {"gross_earnings": 5250000}},
			},
			"approval_state": {
				"company": "Korea Demo Co",
				"workplace": "Seoul HQ",
				"period_start": "2026-05-01",
				"period_end": "2026-05-31",
				"approver": "branch-manager@example.com",
			},
			"notification_state": {
				"company": "Korea Demo Co",
				"workplace": "Seoul HQ",
				"period_start": "2026-05-01",
				"period_end": "2026-05-31",
				"payslip_artifacts_ready": True,
				"kakao_queue_ready": True,
			},
			"expense_state": {
				"company": "Korea Demo Co",
				"workplace": "Seoul HQ",
				"period_start": "2026-05-01",
				"period_end": "2026-05-31",
				"settlement_ready": True,
			},
			"contract_state": {
				"company": "Korea Demo Co",
				"workplace": "Seoul HQ",
				"period_start": "2026-05-01",
				"period_end": "2026-05-31",
				"contracts_reviewed": True,
				"missing_contract_count": 0,
				"stale_contract_count": 0,
			},
		}

		for fieldname, expected_error in [
			("attendance_summary", "attendance_summary.company is required"),
			("payroll_entry", "payroll_entry.company is required"),
			("approval_state", "approval_state.company is required"),
			("notification_state", "notification_state.company is required"),
			("expense_state", "expense_state.company is required"),
			("contract_state", "contract_state.company is required"),
		]:
			with self.subTest(fieldname=fieldname):
				kwargs = {key: dict(value) if isinstance(value, dict) else value for key, value in base_kwargs.items()}
				kwargs[fieldname].pop("company", None)
				with self.assertRaisesRegex(ValueError, expected_error):
					self.mod.build_korea_payroll_closing_session(**kwargs)

		for fieldname, expected_error in [
			("attendance_summary", "attendance_summary.period_start is required"),
			("payroll_entry", "payroll_entry.period_start is required"),
			("approval_state", "approval_state.period_start is required"),
			("notification_state", "notification_state.period_start is required"),
			("expense_state", "expense_state.period_start is required"),
			("contract_state", "contract_state.period_start is required"),
		]:
			with self.subTest(fieldname=fieldname):
				kwargs = {key: dict(value) if isinstance(value, dict) else value for key, value in base_kwargs.items()}
				kwargs[fieldname].pop("period_start", None)
				kwargs[fieldname].pop("start_date", None)
				with self.assertRaisesRegex(ValueError, expected_error):
					self.mod.build_korea_payroll_closing_session(**kwargs)

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

	def test_builds_human_review_audit_event_preview_from_session(self):
		session = self.mod.build_korea_payroll_closing_session(
			company="Korea Demo Co",
			workplace="Seoul HQ",
			period_start="2026-05-01",
			period_end="2026-05-31",
			attendance_summary={"status": "blocked", "unmarked_days": ["2026-05-03"]},
			payroll_entry={"name": "PAY-ENTRY-0001", "company": "Korea Demo Co", "workplace": "Seoul HQ", "start_date": "2026-05-01", "end_date": "2026-05-31"},
			approval_state={"approver": "branch-manager@example.com"},
			notification_state={"payslip_artifacts_ready": True, "kakao_queue_ready": True},
		)

		event = self.mod.build_korea_payroll_closing_audit_event(
			session,
			actor="branch-manager@example.com",
			action="review_blockers",
			note="Attendance exception reviewed with store manager.",
		)

		self.assertEqual(event["contract_type"], "korea_payroll_closing_audit_event_v1")
		self.assertEqual(event["session_contract_type"], "korea_payroll_closing_session_v1")
		self.assertEqual(event["company"], "Korea Demo Co")
		self.assertEqual(event["workplace"], "Seoul HQ")
		self.assertEqual(event["period_start"], "2026-05-01")
		self.assertEqual(event["period_end"], "2026-05-31")
		self.assertEqual(event["session_status"], "blocked")
		self.assertEqual(event["action"], "review_blockers")
		self.assertEqual(event["actor"], "branch-manager@example.com")
		self.assertEqual(event["blocker_codes"], ["attendance_not_ready", "statutory_artifacts_missing"])
		self.assertEqual(event["runtime_action"], "preview_only")
		self.assertTrue(event["requires_runtime_apply"])
		self.assertTrue(event["requires_human_approval"])
		self.assertEqual(event["ai_role"], "assistant_only")
		self.assertFalse(self._contains_forbidden_numeric_score(event))

	def test_audit_event_rejects_invalid_session_actor_and_action(self):
		with self.assertRaisesRegex(ValueError, "session must be a dict"):
			self.mod.build_korea_payroll_closing_audit_event([], actor="ops@example.com", action="review_blockers")

		with self.assertRaisesRegex(ValueError, "session.contract_type must be korea_payroll_closing_session_v1"):
			self.mod.build_korea_payroll_closing_audit_event({"contract_type": "bad"}, actor="ops@example.com", action="review_blockers")

		valid_session = {
			"contract_type": "korea_payroll_closing_session_v1",
			"company": "Korea Demo Co",
			"workplace": "Seoul HQ",
			"period_start": "2026-05-01",
			"period_end": "2026-05-31",
			"status": "blocked",
			"blockers": [{"code": "attendance_not_ready"}],
			"requires_human_approval": True,
			"ai_role": "assistant_only",
		}
		with self.assertRaisesRegex(ValueError, "actor is required"):
			self.mod.build_korea_payroll_closing_audit_event(valid_session, actor=" ", action="review_blockers")
		with self.assertRaisesRegex(ValueError, "actor must be a string"):
			self.mod.build_korea_payroll_closing_audit_event(valid_session, actor=123, action="review_blockers")
		with self.assertRaisesRegex(ValueError, "action must be one of"):
			self.mod.build_korea_payroll_closing_audit_event(valid_session, actor="ops@example.com", action="close_without_review")
		with self.assertRaisesRegex(ValueError, "session.requires_human_approval must be true"):
			self.mod.build_korea_payroll_closing_audit_event({**valid_session, "requires_human_approval": False}, actor="ops@example.com", action="review_blockers")
		with self.assertRaisesRegex(ValueError, "session.blockers is required"):
			self.mod.build_korea_payroll_closing_audit_event({key: value for key, value in valid_session.items() if key != "blockers"}, actor="ops@example.com", action="review_blockers")
		with self.assertRaisesRegex(ValueError, "session.blockers must be a list"):
			self.mod.build_korea_payroll_closing_audit_event({**valid_session, "blockers": None}, actor="ops@example.com", action="review_blockers")
		with self.assertRaisesRegex(ValueError, "session.blockers must be a list"):
			self.mod.build_korea_payroll_closing_audit_event({**valid_session, "blockers": ""}, actor="ops@example.com", action="review_blockers")
		with self.assertRaisesRegex(ValueError, "session.blockers must contain dict items"):
			self.mod.build_korea_payroll_closing_audit_event({**valid_session, "blockers": ["bad"]}, actor="ops@example.com", action="review_blockers")
		with self.assertRaisesRegex(ValueError, "session.blockers.code is required"):
			self.mod.build_korea_payroll_closing_audit_event({**valid_session, "blockers": [{"code": " "}]}, actor="ops@example.com", action="review_blockers")
		with self.assertRaisesRegex(ValueError, "session.blockers.code must be a string"):
			self.mod.build_korea_payroll_closing_audit_event({**valid_session, "blockers": [{"code": 123}]}, actor="ops@example.com", action="review_blockers")
		for malformed_code in [" bad code ", "SAVE()", "unknown_code"]:
			with self.subTest(malformed_code=malformed_code):
				with self.assertRaisesRegex(ValueError, "session.blockers.code must be a known blocker code"):
					self.mod.build_korea_payroll_closing_audit_event(
						{**valid_session, "blockers": [{"code": malformed_code}]},
						actor="ops@example.com",
						action="review_blockers",
					)
		with self.assertRaisesRegex(ValueError, "note must be a string"):
			self.mod.build_korea_payroll_closing_audit_event(valid_session, actor="ops@example.com", action="review_blockers", note={"bad": True})
		with self.assertRaisesRegex(ValueError, "note must not be blank"):
			self.mod.build_korea_payroll_closing_audit_event(valid_session, actor="ops@example.com", action="review_blockers", note="   ")

	def _contains_forbidden_numeric_score(self, value):
		forbidden = {"risk_score", "score", "probability", "success_rate"}
		if isinstance(value, dict):
			return any(key in forbidden or self._contains_forbidden_numeric_score(child) for key, child in value.items())
		if isinstance(value, list):
			return any(self._contains_forbidden_numeric_score(child) for child in value)
		return False


if __name__ == "__main__":
	unittest.main()
