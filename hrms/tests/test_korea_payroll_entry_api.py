#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "payroll_entry_api.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_payroll_entry_api", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


class TestKoreaPayrollEntryApi(unittest.TestCase):
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
		self.payroll_entry = {
			"name": "PAY-ENTRY-API-0001",
			"company": "Korea Demo Co",
			"posting_date": "2026-05-31",
			"start_date": "2026-05-01",
			"end_date": "2026-05-31",
			"salary_slips": [
				{
					"name": "SAL-ENTRY-API-0001",
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
					"name": "SAL-ENTRY-API-0002",
					"employee": "EMP-0002",
					"company": "Korea Demo Co",
					"start_date": "2026-05-01",
					"end_date": "2026-05-31",
					"earnings": [{"salary_component": "Basic Pay", "amount": 2000000}],
				},
			],
		}

	def test_preview_api_accepts_json_payroll_entry_payload_without_frappe_mutation(self):
		batch = self.mod.preview_korea_payroll_entry_statutory_batch(
			payroll_entry=json.dumps(self.payroll_entry),
			policy=json.dumps(self.policy),
		)

		self.assertEqual(batch["contract_type"], "korea_payroll_entry_statutory_preview_v1")
		self.assertEqual(batch["source"], {"doctype": "Payroll Entry", "name": "PAY-ENTRY-API-0001"})
		self.assertEqual(batch["totals"]["gross_earnings"], 5250000)
		self.assertEqual(batch["totals"]["taxable_earnings"], 5050000)
		self.assertEqual(batch["runtime_action"], "preview_only")
		self.assertTrue(batch["requires_runtime_apply"])

	def test_verification_api_builds_vendor_ready_batch_request_from_json_payloads(self):
		request = self.mod.preview_korea_payroll_entry_verification_batch_request(
			payroll_entry=json.dumps(self.payroll_entry),
			policy=json.dumps(self.policy),
			workplace=json.dumps({"name": "Seoul HQ", "business_registration_number": "123-45-67890"}),
			provider=json.dumps({"type": "partner_api", "name": "Payroll Partner"}),
			consent_reference="CONSENT-ENTRY-API-1",
		)

		self.assertEqual(request["contract_type"], "korea_payroll_entry_verification_preview_v1")
		self.assertEqual(request["request_type"], "korea_payroll_entry_verification_batch_v1")
		self.assertEqual(request["provider"]["type"], "partner_api")
		self.assertEqual(request["source"], {"doctype": "Payroll Entry", "name": "PAY-ENTRY-API-0001"})
		self.assertEqual(request["batch_summary"]["salary_slip_count"], 2)
		self.assertTrue(request["requires_human_approval"])
		self.assertEqual(request["runtime_action"], "preview_only")

	def test_default_provider_is_manual_review_and_input_payloads_are_not_mutated(self):
		payroll_entry = json.loads(json.dumps(self.payroll_entry))
		policy = json.loads(json.dumps(self.policy))
		original_payroll_entry = json.loads(json.dumps(payroll_entry))
		original_policy = json.loads(json.dumps(policy))

		request = self.mod.preview_korea_payroll_entry_verification_batch_request(
			payroll_entry=payroll_entry,
			policy=policy,
			workplace={"name": "Seoul HQ"},
		)

		self.assertEqual(request["provider"]["type"], "manual_review")
		self.assertEqual(payroll_entry, original_payroll_entry)
		self.assertEqual(policy, original_policy)

	def test_invalid_payloads_are_rejected_before_runtime_lookup(self):
		with self.assertRaisesRegex(ValueError, "JSON payload is invalid"):
			self.mod.preview_korea_payroll_entry_statutory_batch(
				payroll_entry='{"name":',
				policy=self.policy,
			)

		with self.assertRaisesRegex(ValueError, "policy must be a dict or JSON object"):
			self.mod.preview_korea_payroll_entry_statutory_batch(
				payroll_entry=self.payroll_entry,
				policy="[]",
			)

		with self.assertRaisesRegex(ValueError, "JSON payload is invalid"):
			self.mod.preview_korea_payroll_entry_statutory_batch(
				payroll_entry="PAY-ENTRY-API-0001",
				policy='{"reference":',
			)

		with self.assertRaisesRegex(ValueError, "JSON payload is invalid"):
			self.mod.preview_korea_payroll_entry_verification_batch_request(
				payroll_entry="PAY-ENTRY-API-0001",
				policy=self.policy,
				workplace='{"name":',
			)

		with self.assertRaisesRegex(ValueError, "JSON payload is invalid"):
			self.mod.preview_korea_payroll_entry_verification_batch_request(
				payroll_entry="PAY-ENTRY-API-0001",
				policy=self.policy,
				workplace={"name": "Seoul HQ"},
				provider='{"type":',
			)

	def test_payroll_entry_name_requires_frappe_runtime_in_direct_mode(self):
		with self.assertRaisesRegex(RuntimeError, "Frappe runtime is required"):
			self.mod.preview_korea_payroll_entry_statutory_batch(
				payroll_entry="PAY-ENTRY-API-0001",
				policy=self.policy,
			)

	def test_api_rejects_public_government_provider_route(self):
		with self.assertRaisesRegex(ValueError, "public_government_api"):
			self.mod.preview_korea_payroll_entry_verification_batch_request(
				payroll_entry=self.payroll_entry,
				policy=self.policy,
				workplace={"name": "Seoul HQ"},
				provider={"type": "public_government_api", "name": "Not Default"},
			)


if __name__ == "__main__":
	unittest.main()
