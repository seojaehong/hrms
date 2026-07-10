# -*- coding: utf-8 -*-
"""list_hourly_payroll_proposals 테스트 — FakeFrappe 스텁, framework-free.

급여 마감 준비: Hourly 프로파일 × time_input(period) → 직원별 gross 제안.
결측(시급 미입력·근무시간 미입력)은 숨기지 않고 명단으로 노출되는지 검증.

실행: python3 hrms/tests/test_korea_hourly_wage_proposals.py
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import types
import unittest

MODULE_PATH = (
	pathlib.Path(__file__).resolve().parents[1]
	/ "regional"
	/ "south_korea"
	/ "hourly_wage_api.py"
)


class FakeFrappe(types.ModuleType):
	def __init__(self, profiles, time_inputs):
		super().__init__("frappe")
		self._profiles = profiles
		self._time_inputs = time_inputs
		self.filters_seen = {}

	def whitelist(self):
		return lambda fn: fn

	def get_all(self, doctype, filters=None, fields=None, **kw):
		self.filters_seen[doctype] = dict(filters or {})
		if doctype == "Korea Employment Profile":
			return [dict(p) for p in self._profiles]
		if doctype == "Korea Payroll Time Input":
			return [dict(t) for t in self._time_inputs]
		return []


def _load(profiles, time_inputs):
	fake = FakeFrappe(profiles, time_inputs)
	sys.modules["frappe"] = fake
	spec = importlib.util.spec_from_file_location("hourly_wage_api_stub", MODULE_PATH)
	mod = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(mod)
	return mod, fake


PROFILES = [
	{"employee": "E1", "base_wage": 10030, "scheduled_work_hours_per_week": 20},
	{"employee": "E2", "base_wage": 12000, "scheduled_work_hours_per_week": 40},
	{"employee": "E3", "base_wage": 0, "scheduled_work_hours_per_week": 20},      # 시급 미입력
	{"employee": "E4", "base_wage": 10030, "scheduled_work_hours_per_week": 15},  # time_input 없음
]
TIME_INPUTS = [
	{"employee": "E1", "employee_name": "일번", "part_time_hours": 80, "overtime_hours": 0, "night_hours": 0, "holiday_hours": 0},
	{"employee": "E2", "employee_name": "이번", "part_time_hours": 160, "overtime_hours": 10, "night_hours": 0, "holiday_hours": 0},
]


class TestProposals(unittest.TestCase):
	def setUp(self):
		self.mod, self.fake = _load(PROFILES, TIME_INPUTS)

	def test_proposal_counts_and_missing_lists(self):
		out = self.mod.list_hourly_payroll_proposals("2026-06")
		self.assertEqual([p["employee"] for p in out["proposals"]], ["E1", "E2"])
		self.assertEqual(out["missing_rate"], ["E3"])
		self.assertEqual(out["missing_time_input"], ["E4"])

	def test_e1_amounts(self):
		out = self.mod.list_hourly_payroll_proposals("2026-06")
		p1 = out["proposals"][0]
		comp = {r["component"]: r["amount"] for r in p1["earnings"]}
		# 기본급 80h × 10,030 = 802,400 · 주휴 = 4h × 10,030 × 365/12/7 = 174,331
		self.assertEqual(comp["기본급"], 802400)
		self.assertEqual(comp["주휴수당"], 174331)
		self.assertEqual(p1["gross_pay"], 802400 + 174331)

	def test_e2_overtime(self):
		out = self.mod.list_hourly_payroll_proposals("2026-06")
		p2 = out["proposals"][1]
		comp = {r["component"]: r["amount"] for r in p2["earnings"]}
		self.assertEqual(comp["연장근로수당"], 180000)  # 10 × 12,000 × 1.5

	def test_minimum_wage_flags(self):
		out = self.mod.list_hourly_payroll_proposals("2026-06", minimum_wage=10030)
		flags = {p["employee"]: p["below_minimum_wage"] for p in out["proposals"]}
		self.assertFalse(flags["E1"])  # 10,030 = 최저 → 위반 아님
		self.assertFalse(flags["E2"])

	def test_company_filter_passed(self):
		self.mod.list_hourly_payroll_proposals("2026-06", company="노호")
		self.assertEqual(self.fake.filters_seen["Korea Employment Profile"].get("company"), "노호")
		self.assertEqual(self.fake.filters_seen["Korea Payroll Time Input"].get("company"), "노호")

	def test_empty_period_rejected(self):
		with self.assertRaises(ValueError):
			self.mod.list_hourly_payroll_proposals("  ")


if __name__ == "__main__":
	unittest.main()
