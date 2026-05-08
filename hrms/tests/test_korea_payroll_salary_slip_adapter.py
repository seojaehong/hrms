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
		self.assertEqual(
			payload["deduction_rows"][0],
			{"salary_component": "National Pension", "amount": 150750, "contribution_basis": 3350000},
		)
		self.assertEqual(
			payload["employer_contribution_rows"][-1],
			{"salary_component": "Employment Insurance", "amount": 38525, "contribution_basis": 3350000},
		)

	def test_includes_employer_only_industrial_accident_contribution_row(self):
		policy = {
			**self.policy,
			"industrial_accident_insurance": {
				"basis": "monthly_taxable_wage",
				"employer_rate": "0.007",
			},
		}
		salary_slip = {
			"name": "SAL-SLIP-IAI",
			"employee": "EMP-IAI",
			"company": "Korea Demo Co",
			"start_date": "2026-05-01",
			"end_date": "2026-05-31",
			"earnings": [{"salary_component": "Basic Pay", "amount": 3000000}],
		}

		payload = self.mod.build_korea_salary_slip_statutory_payload(salary_slip=salary_slip, policy=policy)

		self.assertNotIn(
			{"salary_component": "Industrial Accident Insurance", "amount": 0},
			payload["deduction_rows"],
		)
		self.assertIn(
			{"salary_component": "Industrial Accident Insurance", "amount": 21000, "contribution_basis": 3000000},
			payload["employer_contribution_rows"],
		)

	def test_applies_statutory_deductions_to_salary_slip_rows_without_submit_or_send(self):
		salary_slip = SimpleNamespace(
			name="SAL-SLIP-APPLY-1",
			employee="EMP-APPLY",
			company="Korea Demo Co",
			start_date="2026-05-01",
			end_date="2026-05-31",
			earnings=[SimpleNamespace(salary_component="Basic Pay", amount=3000000)],
			deductions=[],
			docstatus=0,
		)
		payload = self.mod.build_korea_salary_slip_statutory_payload(salary_slip=salary_slip, policy=self.policy)

		result = self.mod.apply_korea_statutory_to_salary_slip(
			salary_slip=salary_slip,
			statutory_payload=payload,
			actor="payroll.manager@example.com",
		)

		self.assertEqual(result["contract_type"], "korea_salary_slip_statutory_apply_result_v1")
		self.assertEqual(result["runtime_action"], "runtime_salary_slip_rows_applied")
		self.assertEqual(result["mutation_boundary"], "salary_slip_rows_only_no_submit_no_approve_no_send_no_provider_call")
		self.assertTrue(result["requires_human_approval"])
		self.assertEqual(result["ai_role"], "assistant_only")
		self.assertEqual(result["applied_deduction_count"], 4)
		self.assertEqual(result["salary_slip"], {"doctype": "Salary Slip", "name": "SAL-SLIP-APPLY-1"})
		self.assertEqual(salary_slip.deductions[0].salary_component, "National Pension")
		self.assertEqual(salary_slip.deductions[0].amount, 135000)
		self.assertFalse(hasattr(salary_slip, "submit_called"))
		self.assertFalse(hasattr(salary_slip, "save_called"))

	def test_reapplying_statutory_rows_is_idempotent_and_preserves_unrelated_deductions(self):
		salary_slip = SimpleNamespace(
			name="SAL-SLIP-APPLY-2",
			employee="EMP-APPLY",
			company="Korea Demo Co",
			start_date="2026-05-01",
			end_date="2026-05-31",
			earnings=[SimpleNamespace(salary_component="Basic Pay", amount=3000000)],
			deductions=[SimpleNamespace(salary_component="Loan Repayment", amount=50000)],
			docstatus=0,
		)
		first_payload = self.mod.build_korea_salary_slip_statutory_payload(salary_slip=salary_slip, policy=self.policy)
		self.mod.apply_korea_statutory_to_salary_slip(salary_slip=salary_slip, statutory_payload=first_payload, actor="payroll.manager@example.com")
		second_payload = self.mod.build_korea_salary_slip_statutory_payload(
			salary_slip={
				"name": "SAL-SLIP-APPLY-2",
				"employee": "EMP-APPLY",
				"company": "Korea Demo Co",
				"start_date": "2026-05-01",
				"end_date": "2026-05-31",
				"earnings": [{"salary_component": "Basic Pay", "amount": 4000000}],
			},
			policy=self.policy,
		)

		result = self.mod.apply_korea_statutory_to_salary_slip(
			salary_slip=salary_slip,
			statutory_payload=second_payload,
			actor="payroll.manager@example.com",
		)

		deduction_components = [row.salary_component for row in salary_slip.deductions]
		self.assertEqual(deduction_components.count("National Pension"), 1)
		self.assertIn("Loan Repayment", deduction_components)
		self.assertEqual(result["preserved_deduction_count"], 1)
		self.assertEqual(next(row.amount for row in salary_slip.deductions if row.salary_component == "National Pension"), 180000)

	def test_apply_validates_full_payload_before_mutating_deductions(self):
		class BadEmployerRow:
			def as_dict(self):
				raise RuntimeError("bad employer row")

		salary_slip = SimpleNamespace(
			name="SAL-SLIP-VALIDATE-FIRST",
			employee="EMP-APPLY",
			company="Korea Demo Co",
			start_date="2026-05-01",
			end_date="2026-05-31",
			earnings=[SimpleNamespace(salary_component="Basic Pay", amount=3000000)],
			deductions=[SimpleNamespace(salary_component="Loan Repayment", amount=50000)],
			docstatus=0,
		)
		payload = self.mod.build_korea_salary_slip_statutory_payload(salary_slip=salary_slip, policy=self.policy)
		payload["employer_contribution_rows"] = "bad-payload"

		with self.assertRaisesRegex(ValueError, "statutory_payload.employer_contribution_rows must be a list"):
			self.mod.apply_korea_statutory_to_salary_slip(
				salary_slip=salary_slip,
				statutory_payload=payload,
				actor="payroll.manager@example.com",
			)

		self.assertEqual(len(salary_slip.deductions), 1)
		self.assertEqual(salary_slip.deductions[0].salary_component, "Loan Repayment")

		payload = self.mod.build_korea_salary_slip_statutory_payload(salary_slip=salary_slip, policy=self.policy)
		payload["employer_contribution_rows"] = [BadEmployerRow()]
		with self.assertRaisesRegex(RuntimeError, "bad employer row"):
			self.mod.apply_korea_statutory_to_salary_slip(
				salary_slip=salary_slip,
				statutory_payload=payload,
				actor="payroll.manager@example.com",
			)
		self.assertEqual(len(salary_slip.deductions), 1)
		self.assertEqual(salary_slip.deductions[0].salary_component, "Loan Repayment")

	def test_uses_frappe_document_set_and_append_when_available(self):
		class FakeChildRow(SimpleNamespace):
			def as_dict(self):
				return dict(vars(self))

		class FakeSalarySlip(SimpleNamespace):
			def set(self, key, value):
				setattr(self, key, value)

			def append(self, key, value):
				getattr(self, key).append(SimpleNamespace(**value))

		salary_slip = FakeSalarySlip(
			name="SAL-SLIP-FRAPPE",
			employee="EMP-FRAPPE",
			company="Korea Demo Co",
			start_date="2026-05-01",
			end_date="2026-05-31",
			earnings=[SimpleNamespace(salary_component="Basic Pay", amount=3000000)],
			deductions=[FakeChildRow(salary_component="Loan Repayment", amount=50000, loan="LOAN-1", custom_note="keep me")],
			docstatus=0,
		)
		payload = self.mod.build_korea_salary_slip_statutory_payload(salary_slip=salary_slip, policy=self.policy)

		self.mod.apply_korea_statutory_to_salary_slip(
			salary_slip=salary_slip,
			statutory_payload=payload,
			actor="payroll.manager@example.com",
		)

		self.assertEqual(salary_slip.deductions[0].salary_component, "Loan Repayment")
		self.assertEqual(salary_slip.deductions[0].loan, "LOAN-1")
		self.assertEqual(salary_slip.deductions[0].custom_note, "keep me")
		self.assertEqual(salary_slip.deductions[1].salary_component, "National Pension")
		self.assertEqual(salary_slip.deductions[1].amount, 135000)

	def test_apply_rejects_scope_mismatch_submitted_slip_and_missing_human_actor(self):
		salary_slip = {
			"name": "SAL-SLIP-SCOPE",
			"employee": "EMP-APPLY",
			"company": "Korea Demo Co",
			"start_date": "2026-05-01",
			"end_date": "2026-05-31",
			"earnings": [{"salary_component": "Basic Pay", "amount": 3000000}],
			"deductions": [],
		}
		payload = self.mod.build_korea_salary_slip_statutory_payload(salary_slip=salary_slip, policy=self.policy)

		with self.assertRaisesRegex(ValueError, "actor is required"):
			self.mod.apply_korea_statutory_to_salary_slip(salary_slip=salary_slip, statutory_payload=payload, actor="")

		with self.assertRaisesRegex(ValueError, "salary_slip.name does not match statutory payload source"):
			self.mod.apply_korea_statutory_to_salary_slip(
				salary_slip={**salary_slip, "name": "SAL-SLIP-OTHER"},
				statutory_payload=payload,
				actor="payroll.manager@example.com",
			)

		with self.assertRaisesRegex(ValueError, "submitted Salary Slips cannot be mutated"):
			self.mod.apply_korea_statutory_to_salary_slip(
				salary_slip={**salary_slip, "docstatus": 1},
				statutory_payload=payload,
				actor="payroll.manager@example.com",
			)

		with self.assertRaisesRegex(ValueError, "draft Salary Slips only"):
			self.mod.apply_korea_statutory_to_salary_slip(
				salary_slip={**salary_slip, "docstatus": 2},
				statutory_payload=payload,
				actor="payroll.manager@example.com",
			)

	def test_hook_is_noop_until_operator_sets_strict_apply_flag(self):
		salary_slip = SimpleNamespace(
			name="SAL-SLIP-HOOK",
			employee="EMP-HOOK",
			company="Korea Demo Co",
			start_date="2026-05-01",
			end_date="2026-05-31",
			earnings=[SimpleNamespace(salary_component="Basic Pay", amount=3000000)],
			deductions=[],
			docstatus=0,
		)

		result = self.mod.apply_korea_salary_slip_statutory_hook(salary_slip, method="before_validate")

		self.assertEqual(result["runtime_action"], "skipped")
		self.assertEqual(salary_slip.deductions, [])

		salary_slip.apply_korea_statutory_payroll = 0
		result = self.mod.apply_korea_salary_slip_statutory_hook(salary_slip, method="before_validate")
		self.assertEqual(result["runtime_action"], "skipped")

		salary_slip.apply_korea_statutory_payroll = "true"
		with self.assertRaisesRegex(ValueError, "apply_korea_statutory_payroll must be a bool-like check value"):
			self.mod.apply_korea_salary_slip_statutory_hook(salary_slip, method="before_validate")

		salary_slip.apply_korea_statutory_payroll = True
		salary_slip.korea_statutory_region = "US"
		salary_slip.korea_statutory_payload = self.mod.build_korea_salary_slip_statutory_payload(salary_slip=salary_slip, policy=self.policy)
		salary_slip.korea_statutory_apply_actor = "payroll.manager@example.com"
		with self.assertRaisesRegex(ValueError, "korea_statutory_region must be KR"):
			self.mod.apply_korea_salary_slip_statutory_hook(salary_slip, method="before_validate")

		salary_slip.korea_statutory_region = "KR"
		result = self.mod.apply_korea_salary_slip_statutory_hook(salary_slip, method="before_validate")

		self.assertEqual(result["runtime_action"], "runtime_salary_slip_rows_applied")
		self.assertEqual(len(salary_slip.deductions), 4)

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
