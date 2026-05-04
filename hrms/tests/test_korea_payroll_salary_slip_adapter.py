#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import pathlib
import unittest
from types import SimpleNamespace

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "payroll_salary_slip_adapter.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_payroll_salary_slip_adapter", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


class TestKoreaPayrollSalarySlipAdapter(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()
		self.policy = {
			"reference": "2026-demo-policy",
			"meal_allowance_monthly_non_taxable_limit": 200000,
			"national_pension": {"basis": "monthly_taxable_wage", "employee_rate": 0.045, "employer_rate": 0.045, "floor": 390000, "ceiling": 6170000},
			"health_insurance": {"basis": "monthly_taxable_wage", "employee_rate": 0.03545, "employer_rate": 0.03545},
			"long_term_care_insurance": {"basis": "health_insurance", "employee_rate": 0.1295, "employer_rate": 0.1295},
			"employment_insurance": {"basis": "monthly_taxable_wage", "employee_rate": 0.009, "employer_rate": 0.0115},
		}

	def test_builds_statutory_snapshot_from_salary_slip_shaped_doc(self):
		salary_slip = SimpleNamespace(
			name="SAL-SLIP-0001",
			employee="EMP-0001",
			company="Korea Demo Co",
			start_date="2026-05-01",
			end_date="2026-05-31",
			earnings=[
				SimpleNamespace(salary_component="Basic Pay", amount=3000000),
				SimpleNamespace(salary_component="Meal Allowance", amount=250000),
				SimpleNamespace(salary_component="Overtime Allowance", amount=300000),
			],
		)

		payload = self.mod.build_korea_salary_slip_statutory_payload(salary_slip=salary_slip, policy=self.policy)

		self.assertEqual(payload["source"], {"doctype": "Salary Slip", "name": "SAL-SLIP-0001"})
		self.assertEqual(payload["employee"], "EMP-0001")
		self.assertEqual(payload["period"], {"start_date": "2026-05-01", "end_date": "2026-05-31"})
		self.assertEqual(payload["snapshot"]["taxable_earnings"], 3350000)
		self.assertEqual(payload["deduction_rows"][0], {"salary_component": "National Pension", "amount": 150750})
		self.assertEqual(payload["employer_contribution_rows"][-1], {"salary_component": "Employment Insurance", "amount": 38525})

	def test_builds_vendor_ready_verification_request_without_public_api_default(self):
		salary_slip = {
			"name": "SAL-SLIP-0002",
			"employee": "EMP-0002",
			"company": "Korea Demo Co",
			"start_date": "2026-05-01",
			"end_date": "2026-05-31",
			"earnings": [
				{"salary_component": "Basic Pay", "amount": 3000000},
				{"salary_component": "Meal Allowance", "amount": 200000},
			],
		}

		request = self.mod.build_korea_salary_slip_verification_request(
			salary_slip=salary_slip,
			policy=self.policy,
			workplace={"business_registration_number": "123-45-67890", "name": "Seoul HQ"},
			provider={"type": "paid_vendor_api", "name": "Payroll Verification Partner"},
			consent_reference="CONSENT-1",
		)

		self.assertEqual(request["request_type"], "korea_payroll_verification_v1")
		self.assertEqual(request["provider"]["type"], "paid_vendor_api")
		self.assertEqual(request["period"], {"start_date": "2026-05-01", "end_date": "2026-05-31"})
		self.assertEqual(request["basis"]["policy_reference"], "2026-demo-policy")
		self.assertTrue(request["source"]["statutory_adapter_payload"])

	def test_rejects_missing_salary_component_and_public_government_provider_route(self):
		with self.assertRaisesRegex(ValueError, "earning salary_component is required"):
			self.mod.build_korea_salary_slip_statutory_payload(
				salary_slip={"name": "SAL-SLIP-0003", "earnings": [{"amount": 1000000}]},
				policy=self.policy,
			)

		with self.assertRaisesRegex(ValueError, "salary_slip.earnings must be a list"):
			self.mod.build_korea_salary_slip_statutory_payload(
				salary_slip={"name": "SAL-SLIP-0003", "earnings": None},
				policy=self.policy,
			)

		with self.assertRaisesRegex(ValueError, "salary_slip.start_date is required"):
			self.mod.build_korea_salary_slip_verification_request(
				salary_slip={"name": "SAL-SLIP-0004", "earnings": [{"salary_component": "Basic Pay", "amount": 1000000}]},
				policy=self.policy,
				workplace={"name": "Seoul HQ"},
			)

		with self.assertRaisesRegex(ValueError, "public_government_api"):
			self.mod.build_korea_salary_slip_verification_request(
				salary_slip={
					"name": "SAL-SLIP-0004",
					"start_date": "2026-05-01",
					"end_date": "2026-05-31",
					"earnings": [{"salary_component": "Basic Pay", "amount": 1000000}],
				},
				policy=self.policy,
				workplace={"name": "Seoul HQ"},
				provider={"type": "public_government_api", "name": "Not Default"},
			)


if __name__ == "__main__":
	unittest.main()
