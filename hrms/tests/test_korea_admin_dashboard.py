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

		self.assertEqual([card["key"] for card in dashboard["cards"]], ["open_approvals", "overdue_compliance", "pending_payslips", "unclosed_attendance"])
		self.assertEqual(dashboard["cards"][1]["severity"], "danger")
		self.assertEqual(dashboard["cards"][2]["value"], 10)

	def test_dashboard_status_is_attention_when_any_critical_metric_is_nonzero(self):
		dashboard = self.mod.build_admin_dashboard(metrics={"open_approvals": 0, "overdue_compliance": 1, "pending_payslips": 0, "unclosed_attendance": 0})

		self.assertEqual(dashboard["status"], "Needs Attention")

	def test_missing_metrics_default_to_zero(self):
		dashboard = self.mod.build_admin_dashboard(metrics={})

		self.assertEqual(dashboard["status"], "Ready")
		self.assertTrue(all(card["value"] == 0 for card in dashboard["cards"]))


if __name__ == "__main__":
	unittest.main()
