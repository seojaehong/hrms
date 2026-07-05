#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "statutory_payroll.py"
DEMO_SEED_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "demo_seed.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_statutory_payroll", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


class TestKoreaStatutoryPayroll(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()
		self.policy = {
			"meal_allowance_monthly_non_taxable_limit": 200000,
			"national_pension": {"basis": "monthly_taxable_wage", "employee_rate": 0.045, "employer_rate": 0.045, "floor": 390000, "ceiling": 6170000},
			"health_insurance": {"basis": "monthly_taxable_wage", "employee_rate": 0.03545, "employer_rate": 0.03545},
			"long_term_care_insurance": {"basis": "health_insurance", "employee_rate": 0.1295, "employer_rate": 0.1295},
			"employment_insurance": {"basis": "monthly_taxable_wage", "employee_rate": 0.009, "employer_rate": 0.0115},
		}

	def test_build_reference_snapshot_splits_taxable_meal_allowance_and_social_insurance(self):
		snapshot = self.mod.build_statutory_payroll_snapshot(
			earnings=[
				{"component": "Basic Pay", "amount": 3000000},
				{"component": "Meal Allowance", "amount": 250000},
				{"component": "Overtime Allowance", "amount": 300000},
			],
			policy=self.policy,
		)

		self.assertEqual(snapshot["ordinary_wage"], 3000000)
		self.assertEqual(snapshot["non_taxable_earnings"], 200000)
		self.assertEqual(snapshot["taxable_earnings"], 3350000)
		self.assertEqual(
			snapshot["earnings"],
			[
				{
					"component": "Basic Pay",
					"amount": 3000000,
					"korea_component_category": "Ordinary Wage",
					"ordinary_wage_amount": 3000000,
					"taxable_amount": 3000000,
					"non_taxable_amount": 0,
				},
				{
					"component": "Meal Allowance",
					"amount": 250000,
					"korea_component_category": "Allowance",
					"ordinary_wage_amount": 0,
					"taxable_amount": 50000,
					"non_taxable_amount": 200000,
				},
				{
					"component": "Overtime Allowance",
					"amount": 300000,
					"korea_component_category": "Allowance",
					"ordinary_wage_amount": 0,
					"taxable_amount": 300000,
					"non_taxable_amount": 0,
				},
			],
		)
		self.assertEqual(snapshot["employee_deductions"]["National Pension"], 150750)
		self.assertEqual(snapshot["employee_deductions"]["Health Insurance"], 118758)
		self.assertEqual(snapshot["employee_deductions"]["Long-term Care Insurance"], 15379)
		self.assertEqual(snapshot["employee_deductions"]["Employment Insurance"], 30150)
		self.assertEqual(snapshot["employer_contributions"]["Employment Insurance"], 38525)
		self.assertEqual(snapshot["contribution_bases"]["National Pension"]["employee"], 3350000)
		self.assertEqual(snapshot["contribution_bases"]["Health Insurance"]["employer"], 3350000)
		self.assertEqual(snapshot["contribution_bases"]["Long-term Care Insurance"]["employee"], 118758)
		self.assertEqual(snapshot["contribution_bases"]["Employment Insurance"]["employer"], 3350000)
		self.assertEqual(snapshot["net_reference_pay"], 3234963)

	def test_policy_must_provide_explicit_rates_for_every_statutory_component(self):
		policy = dict(self.policy)
		policy.pop("employment_insurance")

		with self.assertRaisesRegex(ValueError, "employment_insurance policy is required"):
			self.mod.build_statutory_payroll_snapshot(earnings=[{"component": "Basic Pay", "amount": 1000000}], policy=policy)

	def test_non_finite_and_negative_inputs_are_rejected(self):
		with self.assertRaises(ValueError):
			self.mod.build_statutory_payroll_snapshot(earnings=[{"component": "Basic Pay", "amount": float("nan")}], policy=self.policy)

		with self.assertRaises(ValueError):
			self.mod.build_statutory_payroll_snapshot(earnings=[{"component": "Basic Pay", "amount": -1}], policy=self.policy)

		policy = dict(self.policy)
		policy["national_pension"] = {**self.policy["national_pension"], "employee_rate": -0.01}
		with self.assertRaisesRegex(ValueError, "national_pension.employee_rate cannot be negative"):
			self.mod.build_statutory_payroll_snapshot(earnings=[{"component": "Basic Pay", "amount": 1000000}], policy=policy)

	def test_unsupported_policy_basis_is_rejected_instead_of_silently_ignored(self):
		policy = dict(self.policy)
		policy["health_insurance"] = {**self.policy["health_insurance"], "basis": "gross_earnings"}

		with self.assertRaisesRegex(ValueError, "health_insurance.basis must be monthly_taxable_wage"):
			self.mod.build_statutory_payroll_snapshot(earnings=[{"component": "Basic Pay", "amount": 1000000}], policy=policy)

	def test_policy_floor_cannot_exceed_ceiling(self):
		policy = dict(self.policy)
		policy["national_pension"] = {**self.policy["national_pension"], "floor": 2000000, "ceiling": 1000000}

		with self.assertRaisesRegex(ValueError, "national_pension.floor cannot exceed national_pension.ceiling"):
			self.mod.build_statutory_payroll_snapshot(earnings=[{"component": "Basic Pay", "amount": 1500000}], policy=policy)

	def test_fractional_krw_money_inputs_are_rejected_instead_of_rounded(self):
		with self.assertRaisesRegex(ValueError, "earning amount must be an integer KRW amount"):
			self.mod.build_statutory_payroll_snapshot(
				earnings=[{"component": "Basic Pay", "amount": "1000000.50"}],
				policy=self.policy,
			)

		policy = dict(self.policy)
		policy["meal_allowance_monthly_non_taxable_limit"] = "200000.25"
		with self.assertRaisesRegex(ValueError, "meal_allowance_monthly_non_taxable_limit must be an integer KRW amount"):
			self.mod.build_statutory_payroll_snapshot(
				earnings=[{"component": "Basic Pay", "amount": 1000000}],
				policy=policy,
			)

	def test_exponent_style_krw_strings_are_rejected_before_integer_conversion(self):
		with self.assertRaisesRegex(ValueError, "earning amount must be a plain integer KRW amount"):
			self.mod.build_statutory_payroll_snapshot(
				earnings=[{"component": "Basic Pay", "amount": "1e6"}],
				policy=self.policy,
			)

		policy = dict(self.policy)
		policy["meal_allowance_monthly_non_taxable_limit"] = "2e5"
		with self.assertRaisesRegex(ValueError, "meal_allowance_monthly_non_taxable_limit must be a plain integer KRW amount"):
			self.mod.build_statutory_payroll_snapshot(
				earnings=[{"component": "Basic Pay", "amount": 1000000}],
				policy=policy,
			)

	def test_non_numeric_krw_strings_keep_finite_number_error(self):
		with self.assertRaisesRegex(ValueError, "earning amount must be a finite number"):
			self.mod.build_statutory_payroll_snapshot(
				earnings=[{"component": "Basic Pay", "amount": "ten"}],
				policy=self.policy,
			)

	def test_large_integer_like_krw_values_are_preserved_without_float_normalization(self):
		policy = {
			"meal_allowance_monthly_non_taxable_limit": 0,
			"national_pension": {"basis": "monthly_taxable_wage", "employee_rate": "0", "employer_rate": "0"},
			"health_insurance": {"basis": "monthly_taxable_wage", "employee_rate": "0", "employer_rate": "0"},
			"long_term_care_insurance": {"basis": "health_insurance", "employee_rate": "0", "employer_rate": "0"},
			"employment_insurance": {"basis": "monthly_taxable_wage", "employee_rate": "0", "employer_rate": "0"},
		}

		snapshot = self.mod.build_statutory_payroll_snapshot(
			earnings=[{"component": "Basic Pay", "amount": "9007199254740993"}],
			policy=policy,
		)

		self.assertEqual(snapshot["gross_earnings"], 9007199254740993)
		self.assertEqual(snapshot["taxable_earnings"], 9007199254740993)
		self.assertEqual(snapshot["ordinary_wage"], 9007199254740993)

	def test_optional_industrial_accident_insurance_is_employer_only(self):
		policy = {
			**self.policy,
			"industrial_accident_insurance": {
				"basis": "monthly_taxable_wage",
				"employer_rate": "0.007",
			},
		}

		snapshot = self.mod.build_statutory_payroll_snapshot(
			earnings=[{"component": "Basic Pay", "amount": 3000000}],
			policy=policy,
		)

		self.assertNotIn("Industrial Accident Insurance", snapshot["employee_deductions"])
		self.assertEqual(snapshot["employer_contributions"]["Industrial Accident Insurance"], 21000)
		self.assertEqual(snapshot["total_employer_contributions"], 310622)

	def test_industrial_accident_insurance_requires_explicit_basis_and_rejects_employee_rate(self):
		missing_basis_policy = {
			**self.policy,
			"industrial_accident_insurance": {
				"employer_rate": "0.007",
			},
		}
		with self.assertRaisesRegex(ValueError, "industrial_accident_insurance.basis is required"):
			self.mod.build_statutory_payroll_snapshot(earnings=[{"component": "Basic Pay", "amount": 3000000}], policy=missing_basis_policy)

		policy = {
			**self.policy,
			"industrial_accident_insurance": {
				"basis": "monthly_taxable_wage",
				"employee_rate": "0.001",
				"employer_rate": "0.007",
			},
		}

		with self.assertRaisesRegex(ValueError, "industrial_accident_insurance.employee_rate is not supported"):
			self.mod.build_statutory_payroll_snapshot(earnings=[{"component": "Basic Pay", "amount": 3000000}], policy=policy)

	def test_component_presets_are_available_for_safe_salary_component_mapping(self):
		presets = self.mod.load_korea_salary_component_presets()

		self.assertEqual(presets["Basic Pay"]["korea_component_category"], "Ordinary Wage")
		self.assertEqual(presets["National Pension"]["type"], "Deduction")
		self.assertIn("Employment Insurance", presets)
		self.assertEqual(presets["Industrial Accident Insurance"]["korea_component_category"], "Employer Statutory Contribution")
		self.assertEqual(presets["Industrial Accident Insurance"].get("is_company_contribution_only"), 1)

	def test_demo_seed_includes_employer_only_industrial_accident_salary_component(self):
		source = DEMO_SEED_PATH.read_text(encoding="utf-8")

		self.assertIn('"Industrial Accident Insurance"', source)
		self.assertIn('"korea_component_category": "Employer Statutory Contribution"', source)
		self.assertIn('"is_company_contribution_only": 1', source)


if __name__ == "__main__":
	unittest.main()
