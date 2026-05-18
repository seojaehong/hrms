#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "admin_dashboard.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_admin_dashboard", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


class TestKoreaAdminDashboard(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()

	def test_build_dashboard_cards_from_launch_metrics(self):
		dashboard = self.mod.build_admin_dashboard(
			metrics={"open_approvals": 3, "overdue_compliance": 2, "pending_payslips": 10, "unclosed_attendance": 1}
		)

		self.assertEqual(
			[card["key"] for card in dashboard["cards"]],
			[
				"open_approvals",
				"overdue_compliance",
				"pending_payslips",
				"unclosed_attendance",
				"blocked_payroll_closings",
				"payroll_review_audit_logs",
			],
		)
		self.assertEqual(dashboard["cards"][1]["severity"], "danger")
		self.assertEqual(dashboard["cards"][2]["value"], 10)

	def test_dashboard_status_is_attention_when_any_critical_metric_is_nonzero(self):
		dashboard = self.mod.build_admin_dashboard(metrics={"open_approvals": 0, "overdue_compliance": 1, "pending_payslips": 0, "unclosed_attendance": 0})

		self.assertEqual(dashboard["status"], "Needs Attention")

	def test_missing_metrics_default_to_zero(self):
		dashboard = self.mod.build_admin_dashboard(metrics={})

		self.assertEqual(dashboard["status"], "Ready")
		self.assertTrue(all(card["value"] == 0 for card in dashboard["cards"]))

	def test_cards_include_admin_home_action_contracts(self):
		dashboard = self.mod.build_admin_dashboard(metrics={"open_approvals": 3, "pending_payslips": 2})

		approvals = next(card for card in dashboard["cards"] if card["key"] == "open_approvals")
		payslips = next(card for card in dashboard["cards"] if card["key"] == "pending_payslips")
		self.assertEqual(approvals["action"]["action"], "review_approval_inbox")
		self.assertEqual(approvals["action"]["route"], "korea-approval-inbox")
		self.assertTrue(approvals["action"]["enabled"])
		self.assertFalse(approvals["action"]["requires_runtime_apply"])
		self.assertEqual(payslips["action"]["action"], "open_payroll_closing_center")

	def test_payroll_closing_session_blocker_card_routes_to_session_review(self):
		dashboard = self.mod.build_admin_dashboard(metrics={"blocked_payroll_closings": 1})

		closing = next(card for card in dashboard["cards"] if card["key"] == "blocked_payroll_closings")
		self.assertEqual(closing["label"], "Blocked Payroll Closings")
		self.assertEqual(closing["severity"], "danger")
		self.assertEqual(closing["value"], 1)
		self.assertEqual(closing["action"]["action"], "open_payroll_closing_session")
		self.assertEqual(closing["action"]["route"], "korea-payroll-closing-session")
		self.assertTrue(closing["action"]["enabled"])
		self.assertFalse(closing["action"]["requires_runtime_apply"])

	def test_payroll_review_audit_log_card_routes_to_audit_trail(self):
		dashboard = self.mod.build_admin_dashboard(metrics={"payroll_review_audit_logs": 3})

		audit = next(card for card in dashboard["cards"] if card["key"] == "payroll_review_audit_logs")
		self.assertEqual(audit["label"], "Payroll Review Audit Logs")
		self.assertEqual(audit["severity"], "warning")
		self.assertEqual(audit["value"], 3)
		self.assertEqual(audit["action"]["action"], "open_payroll_review_audit_logs")
		self.assertEqual(audit["action"]["route"], "korea-payroll-review-audit-logs")
		self.assertTrue(audit["action"]["enabled"])
		self.assertFalse(audit["action"]["requires_runtime_apply"])

	def test_zero_count_cards_keep_disabled_navigation_actions(self):
		dashboard = self.mod.build_admin_dashboard(metrics={})

		for card in dashboard["cards"]:
			self.assertIn("action", card)
			self.assertFalse(card["action"]["enabled"])
			self.assertFalse(card["action"]["requires_runtime_apply"])

	def test_boolean_metric_values_are_rejected_instead_of_counted_as_one(self):
		with self.assertRaises(ValueError):
			self.mod.build_admin_dashboard(metrics={"open_approvals": True})

	def test_empty_string_metric_values_are_rejected_instead_of_defaulted_to_zero(self):
		for value in ("", "   "):
			with self.subTest(value=repr(value)):
				with self.assertRaisesRegex(ValueError, "open_approvals must be a non-negative integer"):
					self.mod.build_admin_dashboard(metrics={"open_approvals": value})

	def test_exponent_style_metric_values_are_rejected(self):
		with self.assertRaisesRegex(ValueError, "pending_payslips must be a non-negative integer"):
			self.mod.build_admin_dashboard(metrics={"pending_payslips": "1e2"})


if __name__ == "__main__":
	unittest.main()
