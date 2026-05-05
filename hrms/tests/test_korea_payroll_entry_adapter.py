#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import pathlib
import unittest
from types import SimpleNamespace

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "payroll_entry_adapter.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_payroll_entry_adapter", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


class TestKoreaPayrollEntryAdapter(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()
		self.policy = {
			"reference": "2026-demo-policy",
			"meal_allowance_monthly_non_taxable_limit": 200000,
			"national_pension": {"basis": "monthly_taxable_wage", "employee_rate": "0.045", "employer_rate": "0.045"},
			"health_insurance": {"basis": "monthly_taxable_wage", "employee_rate": "0.03545", "employer_rate": "0.03545"},
			"long_term_care_insurance": {"basis": "health_insurance", "employee_rate": "0.1295", "employer_rate": "0.1295"},
			"employment_insurance": {"basis": "monthly_taxable_wage", "employee_rate": "0.009", "employer_rate": "0.0115"},
		}

	def test_builds_payroll_entry_statutory_batch_from_salary_slips(self):
		payroll_entry = SimpleNamespace(
			name="PAY-ENTRY-0001",
			company="Korea Demo Co",
			posting_date="2026-05-31",
			start_date="2026-05-01",
			end_date="2026-05-31",
			salary_slips=[
				{
					"name": "SAL-0001",
					"employee": "EMP-0001",
					"company": "Korea Demo Co",
					"start_date": "2026-05-01",
					"end_date": "2026-05-31",
					"earnings": [
						{"salary_component": "Basic Pay", "amount": 3000000},
						{"salary_component": "Meal Allowance", "amount": 250000},
					],
				},
				{
					"name": "SAL-0002",
					"employee": "EMP-0002",
					"company": "Korea Demo Co",
					"start_date": "2026-05-01",
					"end_date": "2026-05-31",
					"earnings": [{"salary_component": "Basic Pay", "amount": 2000000}],
				},
			],
		)

		batch = self.mod.build_korea_payroll_entry_statutory_batch(payroll_entry=payroll_entry, policy=self.policy)

		self.assertEqual(batch["contract_type"], "korea_payroll_entry_statutory_batch_v1")
		self.assertEqual(batch["source"], {"doctype": "Payroll Entry", "name": "PAY-ENTRY-0001"})
		self.assertEqual(batch["period"], {"start_date": "2026-05-01", "end_date": "2026-05-31", "posting_date": "2026-05-31"})
		self.assertEqual([row["employee"] for row in batch["salary_slip_payloads"]], ["EMP-0001", "EMP-0002"])
		self.assertEqual(batch["totals"]["gross_earnings"], 5250000)
		self.assertEqual(batch["totals"]["taxable_earnings"], 5050000)
		self.assertEqual(batch["totals"]["non_taxable_earnings"], 200000)
		self.assertEqual(batch["totals"]["deductions_by_component"]["National Pension"], 227250)
		self.assertEqual(batch["totals"]["employer_contributions_by_component"]["Employment Insurance"], 58075)
		self.assertTrue(batch["requires_runtime_apply"])

	def test_builds_vendor_ready_batch_verification_request_without_public_api_route(self):
		payroll_entry = {
			"name": "PAY-ENTRY-0002",
			"company": "Korea Demo Co",
			"start_date": "2026-05-01",
			"end_date": "2026-05-31",
			"posting_date": "2026-05-31",
			"salary_slips": [
				{
					"name": "SAL-0003",
					"employee": "EMP-0003",
					"company": "Korea Demo Co",
					"start_date": "2026-05-01",
					"end_date": "2026-05-31",
					"earnings": [{"salary_component": "Basic Pay", "amount": 3000000}],
				}
			],
		}

		request = self.mod.build_korea_payroll_entry_verification_batch_request(
			payroll_entry=payroll_entry,
			policy=self.policy,
			workplace={"name": "Seoul HQ", "business_registration_number": "123-45-67890"},
			provider={"type": "partner_api", "name": "Payroll Partner"},
			consent_reference="CONSENT-BATCH-1",
		)

		self.assertEqual(request["request_type"], "korea_payroll_entry_verification_batch_v1")
		self.assertEqual(request["provider"], {"type": "partner_api", "name": "Payroll Partner"})
		self.assertEqual(request["status"], "pending_external_verification")
		self.assertEqual(request["source"]["doctype"], "Payroll Entry")
		self.assertEqual(request["batch_summary"]["salary_slip_count"], 1)
		self.assertEqual(request["batch_summary"]["total_gross_earnings"], 3000000)
		self.assertTrue(request["requires_human_approval"])

		with self.assertRaisesRegex(ValueError, "public_government_api"):
			self.mod.build_korea_payroll_entry_verification_batch_request(
				payroll_entry=payroll_entry,
				policy=self.policy,
				workplace={"name": "Seoul HQ"},
				provider={"type": "public_government_api", "name": "Not a default"},
			)

	def test_rejects_empty_salary_slip_batches_and_cross_company_slips(self):
		with self.assertRaisesRegex(ValueError, "payroll_entry.salary_slips must not be empty"):
			self.mod.build_korea_payroll_entry_statutory_batch(
				payroll_entry={"name": "PAY-EMPTY", "start_date": "2026-05-01", "end_date": "2026-05-31", "salary_slips": []},
				policy=self.policy,
			)

		with self.assertRaisesRegex(ValueError, "salary_slip.company must match payroll_entry.company"):
			self.mod.build_korea_payroll_entry_statutory_batch(
				payroll_entry={
					"name": "PAY-CROSS",
					"company": "Korea Demo Co",
					"start_date": "2026-05-01",
					"end_date": "2026-05-31",
					"salary_slips": [
						{
							"name": "SAL-CROSS",
							"company": "Other Co",
							"start_date": "2026-05-01",
							"end_date": "2026-05-31",
							"earnings": [{"salary_component": "Basic Pay", "amount": 1000000}],
						}
					],
				},
				policy=self.policy,
			)

	def test_rejects_salary_slips_outside_payroll_entry_period(self):
		with self.assertRaisesRegex(ValueError, "salary_slip period must match payroll_entry period"):
			self.mod.build_korea_payroll_entry_statutory_batch(
				payroll_entry={
					"name": "PAY-PERIOD",
					"company": "Korea Demo Co",
					"start_date": "2026-05-01",
					"end_date": "2026-05-31",
					"salary_slips": [
						{
							"name": "SAL-APRIL",
							"company": "Korea Demo Co",
							"start_date": "2026-04-01",
							"end_date": "2026-04-30",
							"earnings": [{"salary_component": "Basic Pay", "amount": 1000000}],
						}
					],
				},
				policy=self.policy,
			)


if __name__ == "__main__":
	unittest.main()
