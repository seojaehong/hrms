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

	def test_build_korea_wage_statement_preview_groups_required_sections(self):
		statement = self.mod.build_korea_wage_statement_preview(
			salary_slip={
				"name": "SAL-2026-05-0001",
				"employee": "HR-EMP-0001",
				"employee_name": "김민준",
				"company": "노란봉투법 데모",
				"period_start": "2026-05-01",
				"period_end": "2026-05-31",
				"earnings": [
					{"label": "기본급", "amount": "3000000", "basis": "월 고정급"},
					{"label": "식대", "amount": 200000, "basis": "비과세 식대 한도 내"},
				],
				"deductions": [
					{"label": "국민연금", "amount": 135000, "basis": "기준소득월액 x 4.5%"},
					{"label": "소득세", "amount": 80000, "basis": "간이세액표 검토 필요"},
				],
			},
			actor="hr.manager@example.com",
		)

		self.assertEqual(statement["contract_type"], "korea_wage_statement_preview_v1")
		self.assertEqual(statement["runtime_action"], "preview_only")
		self.assertFalse(statement["requires_runtime_apply"])
		self.assertTrue(statement["requires_human_approval"])
		self.assertEqual(statement["ai_role"], "assistant_only")
		self.assertEqual(statement["source_salary_slip"], "SAL-2026-05-0001")
		self.assertEqual(statement["sections"][0]["title"], "지급")
		self.assertEqual(statement["sections"][1]["title"], "공제")
		self.assertEqual(statement["sections"][2]["title"], "산출근거")
		self.assertEqual(statement["gross_pay"], 3200000)
		self.assertEqual(statement["total_deductions"], 215000)
		self.assertEqual(statement["net_pay"], 2985000)
		self.assertEqual(statement["print_labels"]["net_pay"], "실지급액")
		self.assertEqual(statement["mutation_boundary"], "preview_only_no_submit_approve_send_provider_call")

	def test_wage_statement_preview_rejects_fractional_or_exponent_amounts(self):
		base = self._base_salary_slip()
		for bad_amount in (True, "1e6", "1000.5", "Infinity"):
			payload = {**base, "earnings": [{"label": "기본급", "amount": bad_amount, "basis": "월 고정급"}]}
			with self.subTest(bad_amount=bad_amount):
				with self.assertRaises(ValueError):
					self.mod.build_korea_wage_statement_preview(salary_slip=payload, actor="hr.manager@example.com")

	def test_wage_statement_preview_rejects_invalid_period_dates(self):
		for bad_start, bad_end in (
			("2026-02-31", "2026-03-31"),
			("2026-2-01", "2026-10-01"),
			("2026-06-01", "2026-05-31"),
		):
			payload = {**self._base_salary_slip(), "period_start": bad_start, "period_end": bad_end}
			with self.subTest(period_start=bad_start, period_end=bad_end):
				with self.assertRaises(ValueError):
					self.mod.build_korea_wage_statement_preview(salary_slip=payload, actor="hr.manager@example.com")

	def _base_salary_slip(self):
		return {
			"name": "SAL-2026-05-0001",
			"employee": "HR-EMP-0001",
			"company": "노란봉투법 데모",
			"period_start": "2026-05-01",
			"period_end": "2026-05-31",
			"earnings": [{"label": "기본급", "amount": "3000000", "basis": "월 고정급"}],
			"deductions": [],
		}


if __name__ == "__main__":
	unittest.main()
