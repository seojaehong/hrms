#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "payroll_verification.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_payroll_verification", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


class TestKoreaPayrollVerificationProvider(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()
		self.snapshot = {
			"gross_earnings": 3350000,
			"taxable_earnings": 3150000,
			"non_taxable_earnings": 200000,
			"contribution_bases": {
				"National Pension": {"employee": 3150000, "employer": 3150000},
				"Health Insurance": {"employee": 3150000, "employer": 3150000},
			},
			"employee_deductions": {"National Pension": 141750, "Health Insurance": 111668},
			"employer_contributions": {"National Pension": 141750, "Health Insurance": 111668},
			"total_employee_deductions": 253418,
			"total_employer_contributions": 253418,
			"net_reference_pay": 3096582,
			"policy_reference": "2026-vendor-review",
		}

	def test_builds_vendor_ready_verification_request_without_public_api_dependency(self):
		request = self.mod.build_payroll_verification_request(
			snapshot=self.snapshot,
			period={"from_date": "2026-05-01", "to_date": "2026-05-31"},
			workplace={"company": "Seoul Manufacturing", "workplace_management_number": "12345678901"},
			provider={"type": "paid_vendor_api", "name": "example payroll verifier"},
			consent_reference="consent-2026-05",
		)

		self.assertEqual(request["provider"]["type"], "paid_vendor_api")
		self.assertEqual(request["status"], "pending_external_verification")
		self.assertEqual(request["basis"]["total_employee_deductions"], 253418)
		self.assertEqual(request["basis"]["contribution_bases"]["National Pension"]["employee"], 3150000)
		self.assertEqual(request["basis"]["net_reference_pay"], 3096582)
		self.assertEqual(request["consent_reference"], "consent-2026-05")
		self.assertNotIn("public_government_api", repr(request).lower())

	def test_public_government_api_provider_type_is_rejected_as_non_default_route(self):
		with self.assertRaisesRegex(ValueError, "public_government_api is not an allowed payroll verification provider"):
			self.mod.build_payroll_verification_request(
				snapshot=self.snapshot,
				period={"from_date": "2026-05-01", "to_date": "2026-05-31"},
				workplace={"company": "Seoul Manufacturing"},
				provider={"type": "public_government_api", "name": "unsupported public route"},
			)

	def test_verification_result_accepts_provider_evidence_and_finite_amount_deltas(self):
		request = self.mod.build_payroll_verification_request(
			snapshot=self.snapshot,
			period={"from_date": "2026-05-01", "to_date": "2026-05-31"},
			workplace={"company": "Seoul Manufacturing"},
			provider={"type": "partner_api", "name": "labor partner"},
		)

		result = self.mod.normalize_payroll_verification_result(
			request=request,
			provider_result={
				"external_reference": "partner-run-17",
				"status": "needs_review",
				"amount_deltas": {"National Pension": -500},
				"evidence": [{"kind": "partner_report", "reference": "s3://redacted/report.pdf"}],
				"review_notes": "Partner amount differs from internal reference.",
			},
		)

		self.assertEqual(result["status"], "needs_review")
		self.assertEqual(result["provider"]["type"], "partner_api")
		self.assertEqual(result["amount_deltas"]["National Pension"], -500)
		self.assertEqual(result["evidence"][0]["kind"], "partner_report")

	def test_verification_request_preserves_large_integer_money_without_float_corruption(self):
		snapshot = dict(self.snapshot)
		snapshot["gross_earnings"] = "9007199254740993"

		request = self.mod.build_payroll_verification_request(
			snapshot=snapshot,
			period={"from_date": "2026-05-01", "to_date": "2026-05-31"},
			workplace={"company": "Seoul Manufacturing"},
			provider={"type": "owned_connector_service", "name": "internal verifier"},
		)

		self.assertEqual(request["basis"]["gross_earnings"], 9007199254740993)

	def test_fractional_money_inputs_are_rejected_instead_of_bankers_rounded(self):
		snapshot = dict(self.snapshot)
		snapshot["net_reference_pay"] = "3096582.5"

		with self.assertRaisesRegex(ValueError, "snapshot.net_reference_pay must be an integer KRW amount"):
			self.mod.build_payroll_verification_request(
				snapshot=snapshot,
				period={"from_date": "2026-05-01", "to_date": "2026-05-31"},
				workplace={"company": "Seoul Manufacturing"},
				provider={"type": "owned_connector_service", "name": "internal verifier"},
			)

	def test_verification_request_rejects_fractional_contribution_basis_amounts(self):
		snapshot = dict(self.snapshot)
		snapshot["contribution_bases"] = {"National Pension": {"employee": "3150000.5", "employer": 3150000}}

		with self.assertRaisesRegex(ValueError, "snapshot.contribution_bases.National Pension.employee must be an integer KRW amount"):
			self.mod.build_payroll_verification_request(
				snapshot=snapshot,
				period={"from_date": "2026-05-01", "to_date": "2026-05-31"},
				workplace={"company": "Seoul Manufacturing"},
				provider={"type": "owned_connector_service", "name": "internal verifier"},
			)

	def test_verification_result_rejects_unknown_status_and_non_finite_deltas(self):
		request = self.mod.build_payroll_verification_request(
			snapshot=self.snapshot,
			period={"from_date": "2026-05-01", "to_date": "2026-05-31"},
			workplace={"company": "Seoul Manufacturing"},
			provider={"type": "owned_connector_service", "name": "internal verifier"},
		)

		with self.assertRaisesRegex(ValueError, "status must be one of"):
			self.mod.normalize_payroll_verification_result(request=request, provider_result={"status": "auto_approved"})

		with self.assertRaisesRegex(ValueError, "amount_deltas.National Pension must be a finite number"):
			self.mod.normalize_payroll_verification_result(
				request=request,
				provider_result={"status": "verified", "amount_deltas": {"National Pension": float("nan")}},
			)


if __name__ == "__main__":
	unittest.main()
