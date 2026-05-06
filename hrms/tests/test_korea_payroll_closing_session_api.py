#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "payroll_closing_session_api.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_payroll_closing_session_api", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


class TestKoreaPayrollClosingSessionApi(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()
		self.attendance_summary = {
			"company": "Korea Demo Co",
			"workplace": "Seoul HQ",
			"period_start": "2026-05-01",
			"period_end": "2026-05-31",
			"status": "ready",
			"employee_count": 2,
			"unmarked_days": [],
		}
		self.payroll_entry = {
			"name": "PAY-ENTRY-API-0001",
			"company": "Korea Demo Co",
			"workplace": "Seoul HQ",
			"start_date": "2026-05-01",
			"end_date": "2026-05-31",
			"salary_slips": [
				{"name": "SAL-API-0001", "employee": "EMP-0001", "company": "Korea Demo Co", "workplace": "Seoul HQ", "status": "Submitted"},
				{"name": "SAL-API-0002", "employee": "EMP-0002", "company": "Korea Demo Co", "workplace": "Seoul HQ", "status": "Submitted"},
			],
			"statutory_batch_payload": {"totals": {"gross_earnings": 5250000, "total_employee_deductions": 420000}},
		}
		self.approval_state = {
			"company": "Korea Demo Co",
			"workplace": "Seoul HQ",
			"period_start": "2026-05-01",
			"period_end": "2026-05-31",
			"approver": "branch-manager@example.com",
			"status": "pending_review",
		}
		self.notification_state = {
			"company": "Korea Demo Co",
			"workplace": "Seoul HQ",
			"period_start": "2026-05-01",
			"period_end": "2026-05-31",
			"payslip_artifacts_ready": True,
			"kakao_queue_ready": True,
			"recipient_count": 2,
		}

	def test_preview_api_builds_payroll_closing_session_from_json_payloads(self):
		session = self.mod.preview_korea_payroll_closing_session(
			company="Korea Demo Co",
			workplace="Seoul HQ",
			period_start="2026-05-01",
			period_end="2026-05-31",
			attendance_summary=json.dumps(self.attendance_summary),
			payroll_entry=json.dumps(self.payroll_entry),
			approval_state=json.dumps(self.approval_state),
			notification_state=json.dumps(self.notification_state),
		)

		self.assertEqual(session["contract_type"], "korea_payroll_closing_session_preview_v1")
		self.assertEqual(session["session_contract_type"], "korea_payroll_closing_session_v1")
		self.assertEqual(session["status"], "review_ready")
		self.assertEqual(session["runtime_action"], "preview_only")
		self.assertTrue(session["requires_runtime_apply"])
		self.assertTrue(session["requires_human_approval"])
		self.assertEqual(session["ai_role"], "assistant_only")
		self.assertEqual(session["source"], {"doctype": "Payroll Entry", "name": "PAY-ENTRY-API-0001"})
		self.assertEqual(session["audit_preview"]["runtime_action"], "preview_only")

	def test_preview_api_accepts_expense_state_json_payload(self):
		session = self.mod.preview_korea_payroll_closing_session(
			company="Korea Demo Co",
			workplace="Seoul HQ",
			period_start="2026-05-01",
			period_end="2026-05-31",
			attendance_summary=self.attendance_summary,
			payroll_entry=self.payroll_entry,
			approval_state=self.approval_state,
			notification_state=self.notification_state,
			expense_state=json.dumps(
				{
					"company": "Korea Demo Co",
					"workplace": "Seoul HQ",
					"period_start": "2026-05-01",
					"period_end": "2026-05-31",
					"settlement_ready": False,
					"open_claim_count": 2,
					"approved_unpaid_count": 1,
				}
			),
		)

		self.assertEqual(session["status"], "blocked")
		self.assertIn("expense_settlement_not_ready", [blocker["code"] for blocker in session["blockers"]])
		self.assertEqual(session["expense_state"]["open_claim_count"], 2)
		self.assertEqual(session["runtime_action"], "preview_only")

	def test_preview_api_accepts_contract_state_json_payload(self):
		session = self.mod.preview_korea_payroll_closing_session(
			company="Korea Demo Co",
			workplace="Seoul HQ",
			period_start="2026-05-01",
			period_end="2026-05-31",
			attendance_summary=self.attendance_summary,
			payroll_entry=self.payroll_entry,
			approval_state=self.approval_state,
			notification_state=self.notification_state,
			contract_state=json.dumps(
				{
					"company": "Korea Demo Co",
					"workplace": "Seoul HQ",
					"period_start": "2026-05-01",
					"period_end": "2026-05-31",
					"contracts_reviewed": False,
					"missing_contract_count": 1,
					"stale_contract_count": 0,
				}
			),
		)

		self.assertEqual(session["status"], "blocked")
		self.assertIn("employment_contracts_not_ready", [blocker["code"] for blocker in session["blockers"]])
		self.assertEqual(session["contract_state"]["missing_contract_count"], 1)
		self.assertEqual(session["runtime_action"], "preview_only")

	def test_preview_api_does_not_mutate_caller_payloads(self):
		attendance = json.loads(json.dumps(self.attendance_summary))
		payroll = json.loads(json.dumps(self.payroll_entry))
		approval = json.loads(json.dumps(self.approval_state))
		notification = json.loads(json.dumps(self.notification_state))
		contract = {
			"company": "Korea Demo Co",
			"workplace": "Seoul HQ",
			"period_start": "2026-05-01",
			"period_end": "2026-05-31",
			"contracts_reviewed": True,
		}
		originals = json.loads(json.dumps([attendance, payroll, approval, notification, contract]))

		session = self.mod.preview_korea_payroll_closing_session(
			company="Korea Demo Co",
			workplace="Seoul HQ",
			period_start="2026-05-01",
			period_end="2026-05-31",
			attendance_summary=attendance,
			payroll_entry=payroll,
			approval_state=approval,
			notification_state=notification,
			contract_state=contract,
		)

		self.assertEqual([attendance, payroll, approval, notification, contract], originals)
		session["payroll_artifacts"]["salary_slips"][0]["name"] = "MUTATED"
		self.assertEqual(payroll["salary_slips"][0]["name"], "SAL-API-0001")

	def test_invalid_json_payloads_are_rejected_before_delegation(self):
		with self.assertRaisesRegex(ValueError, "JSON payload is invalid"):
			self.mod.preview_korea_payroll_closing_session(
				company="Korea Demo Co",
				workplace="Seoul HQ",
				period_start="2026-05-01",
				period_end="2026-05-31",
				attendance_summary='{"status":',
				payroll_entry=self.payroll_entry,
				approval_state=self.approval_state,
				notification_state=self.notification_state,
			)

		with self.assertRaisesRegex(ValueError, "payroll_entry must be a dict or JSON object"):
			self.mod.preview_korea_payroll_closing_session(
				company="Korea Demo Co",
				workplace="Seoul HQ",
				period_start="2026-05-01",
				period_end="2026-05-31",
				attendance_summary=self.attendance_summary,
				payroll_entry="[]",
				approval_state=self.approval_state,
				notification_state=self.notification_state,
			)

		with self.assertRaisesRegex(ValueError, "expense_state must be a dict or JSON object"):
			self.mod.preview_korea_payroll_closing_session(
				company="Korea Demo Co",
				workplace="Seoul HQ",
				period_start="2026-05-01",
				period_end="2026-05-31",
				attendance_summary=self.attendance_summary,
				payroll_entry=self.payroll_entry,
				approval_state=self.approval_state,
				notification_state=self.notification_state,
				expense_state=[],
			)

		with self.assertRaisesRegex(ValueError, "contract_state must be a dict or JSON object"):
			self.mod.preview_korea_payroll_closing_session(
				company="Korea Demo Co",
				workplace="Seoul HQ",
				period_start="2026-05-01",
				period_end="2026-05-31",
				attendance_summary=self.attendance_summary,
				payroll_entry=self.payroll_entry,
				approval_state=self.approval_state,
				notification_state=self.notification_state,
				contract_state="[]",
			)

	def test_preview_api_preserves_core_fail_closed_validation(self):
		with self.assertRaisesRegex(ValueError, "payroll_entry.company must match session company"):
			payroll_entry = json.loads(json.dumps(self.payroll_entry))
			payroll_entry["company"] = "Other Co"
			self.mod.preview_korea_payroll_closing_session(
				company="Korea Demo Co",
				workplace="Seoul HQ",
				period_start="2026-05-01",
				period_end="2026-05-31",
				attendance_summary=self.attendance_summary,
				payroll_entry=payroll_entry,
				approval_state=self.approval_state,
				notification_state=self.notification_state,
			)


if __name__ == "__main__":
	unittest.main()
