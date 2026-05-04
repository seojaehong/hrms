#!/usr/bin/env python3
"""Direct-run tests for South Korea employment contract helpers."""

from __future__ import annotations

import datetime as dt
import importlib.util
import pathlib
import unittest

MODULE_PATH = (
	pathlib.Path(__file__).resolve().parents[1]
	/ "regional"
	/ "south_korea"
	/ "employment_contract.py"
)


def load_module():
	spec = importlib.util.spec_from_file_location("korea_employment_contract", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


class TestKoreaEmploymentContract(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()

	def test_build_contract_snapshot_normalizes_required_terms(self):
		contract = self.mod.build_contract_snapshot(
			employee="EMP-001",
			company="Seo Co",
			workplace="Seoul HQ",
			start_date=dt.date(2026, 1, 1),
			job_title="Engineer",
			employment_type="Regular",
			working_hours_per_week=40,
			monthly_wage=3_000_000,
			pay_day=25,
		)

		self.assertEqual(contract["employee"], "EMP-001")
		self.assertEqual(contract["contract_type"], "Indefinite")
		self.assertEqual(contract["start_date"], "2026-01-01")
		self.assertEqual(contract["working_hours_per_week"], 40.0)
		self.assertEqual(contract["monthly_wage"], 3000000)
		self.assertEqual(contract["required_terms_complete"], True)
		self.assertEqual(contract["missing_terms"], [])

	def test_fixed_term_contract_requires_end_date_after_start_date(self):
		with self.assertRaises(ValueError):
			self.mod.build_contract_snapshot(
				employee="EMP-001",
				company="Seo Co",
				workplace="Seoul HQ",
				start_date=dt.date(2026, 1, 1),
				end_date=dt.date(2025, 12, 31),
				job_title="Engineer",
				employment_type="Fixed Term",
				working_hours_per_week=40,
				monthly_wage=3_000_000,
				pay_day=25,
			)

	def test_missing_required_terms_are_reported_without_frappe_runtime(self):
		contract = self.mod.build_contract_snapshot(
			employee="EMP-002",
			company="Seo Co",
			workplace="",
			start_date=dt.date(2026, 2, 1),
			job_title="",
			employment_type="Part Time",
			working_hours_per_week=20,
			monthly_wage=1_200_000,
			pay_day=10,
		)

		self.assertFalse(contract["required_terms_complete"])
		self.assertEqual(contract["missing_terms"], ["workplace", "job_title"])

	def test_signature_hash_is_deterministic_for_reviewed_contract_payload(self):
		first = self.mod.build_contract_snapshot(
			employee="EMP-001",
			company="Seo Co",
			workplace="Seoul HQ",
			start_date=dt.date(2026, 1, 1),
			job_title="Engineer",
			employment_type="Regular",
			working_hours_per_week=40,
			monthly_wage=3_000_000,
			pay_day=25,
		)
		second = dict(reversed(list(first.items())))

		self.assertEqual(first["signature_hash"], self.mod.contract_signature_hash(second))


if __name__ == "__main__":
	unittest.main()
