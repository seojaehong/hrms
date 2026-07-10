# -*- coding: utf-8 -*-
"""고지 대사 API 테스트 — FakeFrappe 스텁, framework-free.

실행: python3 hrms/tests/test_korea_insurance_reconciliation_api.py
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import types
import unittest

MODULE_PATH = (
	pathlib.Path(__file__).resolve().parents[1]
	/ "regional"
	/ "south_korea"
	/ "insurance_reconciliation_api.py"
)


class FakeFrappe(types.ModuleType):
	def __init__(self, slips, details):
		super().__init__("frappe")
		self._slips = slips
		self._details = details
		self.filters_seen = {}

	def whitelist(self):
		return lambda fn: fn

	def get_all(self, doctype, filters=None, fields=None, **kw):
		self.filters_seen[doctype] = filters
		if doctype == "Salary Slip":
			return [dict(s) for s in self._slips]
		if doctype == "Salary Detail":
			parents = set((filters or {}).get("parent", [None, []])[1])
			return [dict(d) for d in self._details if d["parent"] in parents]
		return []


def _load(slips, details):
	fake = FakeFrappe(slips, details)
	sys.modules["frappe"] = fake
	spec = importlib.util.spec_from_file_location("ins_recon_api_stub", MODULE_PATH)
	mod = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(mod)
	return mod, fake


SLIPS = [
	{"name": "SS-1", "employee": "천시원", "employee_name": "천시원"},
	{"name": "SS-2", "employee": "김하늘", "employee_name": "김하늘"},
]
DETAILS = [
	{"parent": "SS-1", "salary_component": "국민연금", "amount": 187730},
	{"parent": "SS-1", "salary_component": "소득세", "amount": 50000},
	{"parent": "SS-2", "salary_component": "국민연금", "amount": 90000},
	{"parent": "SS-2", "salary_component": "고용보험", "amount": 27000},
]


class TestReconcilePeriod(unittest.TestCase):
	def setUp(self):
		self.mod, self.fake = _load(SLIPS, DETAILS)

	def test_kuukuu_overdeduction_flagged(self):
		notified = [
			{"employee": "천시원", "national_pension": 166500},
			{"employee": "김하늘", "national_pension": 90000, "employment_insurance": 27000},
		]
		out = self.mod.reconcile_period_contributions(2026, 6, notified)
		self.assertEqual(out["period"], "2026-06")
		self.assertEqual(out["employee_count"], 2)
		recon = out["reconciliation"]
		self.assertFalse(recon["ok"])
		self.assertEqual(len(recon["diffs"]), 1)
		self.assertEqual(recon["diffs"][0]["delta"], 21230)
		self.assertIn("+21,230", out["summary_ko"])
		# 소득세는 4대 아님 → unmapped 정보
		self.assertEqual(out["unmapped_deductions"][0]["component"], "소득세")

	def test_notified_json_string_accepted(self):
		notified = json.dumps([
			{"employee": "천시원", "national_pension": 187730},
			{"employee": "김하늘", "national_pension": 90000},
		])
		out = self.mod.reconcile_period_contributions("2026", "6", notified)
		self.assertTrue(out["reconciliation"]["ok"])

	def test_month_bounds_filter(self):
		self.mod.reconcile_period_contributions(2026, 2, [])
		f = self.fake.filters_seen["Salary Slip"]
		self.assertEqual(f["start_date"], ["between", ["2026-02-01", "2026-02-28"]])
		self.assertEqual(f["docstatus"], 1)

	def test_company_filter(self):
		self.mod.reconcile_period_contributions(2026, 6, [], company="노호")
		self.assertEqual(self.fake.filters_seen["Salary Slip"].get("company"), "노호")

	def test_invalid_month_rejected(self):
		with self.assertRaises(ValueError):
			self.mod.reconcile_period_contributions(2026, 13, [])

	def test_notified_must_be_list(self):
		with self.assertRaises(ValueError):
			self.mod.reconcile_period_contributions(2026, 6, {"employee": "x"})


if __name__ == "__main__":
	unittest.main()
