#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "payroll_salary_slip_api.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_payroll_salary_slip_api", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


class TestKoreaPayrollSalarySlipApi(unittest.TestCase):
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
		self.salary_slip = {
			"name": "SAL-SLIP-API-0001",
			"employee": "EMP-0001",
			"company": "Korea Demo Co",
			"start_date": "2026-05-01",
			"end_date": "2026-05-31",
			"earnings": [
				{"salary_component": "Basic Pay", "amount": 3000000},
				{"salary_component": "Meal Allowance", "amount": 250000},
			],
		}

	def test_preview_api_accepts_json_payloads_without_frappe_mutation(self):
		payload = self.mod.preview_korea_salary_slip_statutory_payload(
			salary_slip=json.dumps(self.salary_slip),
			policy=json.dumps(self.policy),
		)

		self.assertEqual(payload["contract_type"], "korea_salary_slip_statutory_preview_v1")
		self.assertEqual(payload["source"], {"doctype": "Salary Slip", "name": "SAL-SLIP-API-0001"})
		self.assertEqual(payload["snapshot"]["taxable_earnings"], 3050000)
		self.assertTrue(payload["requires_runtime_apply"])
		self.assertEqual(payload["runtime_action"], "preview_only")

	def test_verification_api_builds_vendor_ready_request_from_json_payloads(self):
		request = self.mod.preview_korea_salary_slip_verification_request(
			salary_slip=json.dumps(self.salary_slip),
			policy=json.dumps(self.policy),
			workplace=json.dumps({"name": "Seoul HQ", "business_registration_number": "123-45-67890"}),
			provider=json.dumps({"type": "partner_api", "name": "Payroll Partner"}),
			consent_reference="CONSENT-API-1",
		)

		self.assertEqual(request["contract_type"], "korea_salary_slip_verification_preview_v1")
		self.assertEqual(request["request_type"], "korea_payroll_verification_v1")
		self.assertEqual(request["provider"]["type"], "partner_api")
		self.assertEqual(request["source"]["doctype"], "Salary Slip")
		self.assertTrue(request["requires_runtime_apply"])

	def test_default_provider_is_manual_review_and_input_payloads_are_not_mutated(self):
		salary_slip = dict(self.salary_slip)
		salary_slip["earnings"] = [dict(row) for row in self.salary_slip["earnings"]]
		policy = dict(self.policy)
		workplace = {"name": "Seoul HQ"}
		original_salary_slip = dict(salary_slip)
		original_salary_slip["earnings"] = [dict(row) for row in salary_slip["earnings"]]
		original_policy = dict(policy)

		request = self.mod.preview_korea_salary_slip_verification_request(
			salary_slip=salary_slip,
			policy=policy,
			workplace=workplace,
		)

		self.assertEqual(request["provider"]["type"], "manual_review")
		self.assertEqual(salary_slip, original_salary_slip)
		self.assertEqual(policy, original_policy)

	def test_invalid_json_payload_is_rejected_before_runtime_lookup(self):
		with self.assertRaisesRegex(ValueError, "JSON payload is invalid"):
			self.mod.preview_korea_salary_slip_statutory_payload(
				salary_slip='{"name":',
				policy=self.policy,
			)

		with self.assertRaisesRegex(ValueError, "policy must be a dict or JSON object"):
			self.mod.preview_korea_salary_slip_statutory_payload(
				salary_slip=self.salary_slip,
				policy="[]",
			)

	def test_salary_slip_name_requires_frappe_runtime_in_direct_mode(self):
		with self.assertRaisesRegex(RuntimeError, "Frappe runtime is required"):
			self.mod.preview_korea_salary_slip_statutory_payload(
				salary_slip="SAL-SLIP-API-0001",
				policy=self.policy,
			)

	def test_api_rejects_public_government_provider_route(self):
		with self.assertRaisesRegex(ValueError, "public_government_api"):
			self.mod.preview_korea_salary_slip_verification_request(
				salary_slip=self.salary_slip,
				policy=self.policy,
				workplace={"name": "Seoul HQ"},
				provider={"type": "public_government_api", "name": "Not Default"},
			)


if __name__ == "__main__":
	unittest.main()
