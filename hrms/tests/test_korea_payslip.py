#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "payslip.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_payslip", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


class TestKoreaPayslip(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()

	def test_build_payslip_snapshot_groups_earnings_and_deductions(self):
		payslip = self.mod.build_payslip_snapshot(
			employee="EMP-001",
			period="2026-05",
			earnings=[{"label": "Basic Pay", "amount": 3000000}, {"label": "Meal Allowance", "amount": 200000}],
			deductions=[{"label": "National Pension", "amount": 135000}, {"label": "Income Tax", "amount": 80000}],
		)

		self.assertEqual(payslip["gross_pay"], 3200000)
		self.assertEqual(payslip["total_deductions"], 215000)
		self.assertEqual(payslip["net_pay"], 2985000)
		self.assertEqual(payslip["sections"][0]["title"], "Earnings")
		self.assertEqual(payslip["sections"][1]["title"], "Deductions")

	def test_public_view_masks_employee_identifier_and_keeps_totals(self):
		payslip = self.mod.build_payslip_snapshot(employee="EMP-001234", period="2026-05", earnings=[{"label": "Basic Pay", "amount": 1000}], deductions=[])

		view = self.mod.build_employee_payslip_view(payslip)

		self.assertEqual(view["employee"], "EMP-****34")
		self.assertEqual(view["net_pay"], 1000)
		self.assertNotIn("checksum", view)

	def test_negative_line_amount_is_rejected(self):
		with self.assertRaises(ValueError):
			self.mod.build_payslip_snapshot(employee="EMP-001", period="2026-05", earnings=[{"label": "Basic Pay", "amount": -1}], deductions=[])


if __name__ == "__main__":
	unittest.main()
