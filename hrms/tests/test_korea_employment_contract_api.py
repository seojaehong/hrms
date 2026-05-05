#!/usr/bin/env python3
"""Direct-run tests for South Korea employment contract preview API."""

from __future__ import annotations

import importlib.util
import json
import pathlib
import unittest

MODULE_PATH = (
	pathlib.Path(__file__).resolve().parents[1]
	/ "regional"
	/ "south_korea"
	/ "employment_contract_api.py"
)


def load_module():
	spec = importlib.util.spec_from_file_location("korea_employment_contract_api", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


class TestKoreaEmploymentContractPreviewAPI(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()

	def test_previews_contract_snapshot_from_json_profile_without_mutation(self):
		profile = {
			"employee": " EMP-001 ",
			"company": "Seo Co",
			"workplace": "Seoul HQ",
			"start_date": "2026-01-01",
			"job_title": "Engineer",
			"employment_type": "Regular",
			"working_hours_per_week": "40",
			"monthly_wage": "3000000",
			"pay_day": "25",
			"probation_months": "3",
		}

		preview = self.mod.preview_korea_employment_contract_snapshot(
			employment_profile=json.dumps(profile, ensure_ascii=False)
		)
		preview["contract_snapshot"]["employee"] = "MUTATED"

		self.assertEqual(preview["contract_type"], "korea_employment_contract_preview_v1")
		self.assertEqual(preview["runtime_action"], "preview_only")
		self.assertFalse(preview["requires_runtime_apply"])
		self.assertEqual(preview["contract_snapshot"]["contract_type"], "Indefinite")
		self.assertEqual(preview["contract_snapshot"]["start_date"], "2026-01-01")
		self.assertEqual(preview["contract_snapshot"]["monthly_wage"], 3000000)
		self.assertEqual(profile["employee"], " EMP-001 ")

	def test_previews_fixed_term_contract_with_end_date_and_required_term_gaps(self):
		preview = self.mod.preview_korea_employment_contract_snapshot(
			employment_profile={
				"employee": "EMP-002",
				"company": "Seo Co",
				"workplace": "",
				"start_date": "2026-02-01",
				"end_date": "2026-12-31",
				"job_title": "",
				"employment_type": "Fixed Term",
				"working_hours_per_week": 20,
				"monthly_wage": 1200000,
				"pay_day": 10,
			}
		)

		self.assertEqual(preview["contract_snapshot"]["contract_type"], "Fixed Term")
		self.assertEqual(preview["contract_snapshot"]["end_date"], "2026-12-31")
		self.assertFalse(preview["contract_snapshot"]["required_terms_complete"])
		self.assertEqual(preview["contract_snapshot"]["missing_terms"], ["workplace", "job_title"])

	def test_rejects_invalid_json_and_invalid_dates_before_runtime_apply(self):
		with self.assertRaisesRegex(ValueError, "JSON payload is invalid"):
			self.mod.preview_korea_employment_contract_snapshot(employment_profile="{not-json")

		with self.assertRaisesRegex(ValueError, "start_date must be an ISO date"):
			self.mod.preview_korea_employment_contract_snapshot(
				employment_profile={
					"employee": "EMP-003",
					"company": "Seo Co",
					"workplace": "Seoul HQ",
					"start_date": "2026/01/01",
					"job_title": "Engineer",
					"employment_type": "Regular",
					"working_hours_per_week": 40,
					"monthly_wage": 3000000,
					"pay_day": 25,
				}
			)

		with self.assertRaisesRegex(ValueError, "employment_profile must be a dict or JSON object"):
			self.mod.preview_korea_employment_contract_snapshot(employment_profile=[])


if __name__ == "__main__":
	unittest.main()
