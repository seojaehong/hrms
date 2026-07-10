# -*- coding: utf-8 -*-
"""시급제 월 급여 API(hourly_wage_api) 테스트 — framework-free.

체인 E2E: 세션(출퇴근) → 일별 가산(§56) → 월 집계+주휴(§55) → earnings.
실행: python3 hrms/tests/test_korea_hourly_wage_api.py
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import unittest

MODULE_PATH = (
	pathlib.Path(__file__).resolve().parents[1]
	/ "regional"
	/ "south_korea"
	/ "hourly_wage_api.py"
)
_spec = importlib.util.spec_from_file_location("hourly_wage_api", MODULE_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

estimate = _mod.estimate_hourly_monthly_payroll

# 주 20h 파트타이머, 시급 10,000 — 4일 × 5h(09:00~14:00, 무휴게)
BASIC_SESSIONS = [
	{"work_date": f"2026-06-0{d}", "start_time": "09:00", "end_time": "14:00"}
	for d in (1, 2, 3, 4)
]


class TestBasicMonth(unittest.TestCase):
	def test_regular_only(self):
		out = estimate(BASIC_SESSIONS, hourly_rate=10000, contracted_weekly_hours=20)
		comp = {r["component"]: r["amount"] for r in out["earnings"]}
		# 기본급 = 4일 × 5h × 10,000 = 200,000
		self.assertEqual(comp["기본급"], 200000)
		# 주휴(주 20h → 4h × 10,000 × 365/12/7) = 173,810
		self.assertEqual(comp["주휴수당"], 173810)
		self.assertEqual(out["gross_pay"], 200000 + 173810)
		self.assertEqual(len(out["daily"]), 4)
		self.assertIsNone(out["below_minimum_wage"])

	def test_json_string_sessions(self):
		out = estimate(json.dumps(BASIC_SESSIONS), hourly_rate=10000, contracted_weekly_hours=20)
		self.assertEqual(out["gross_pay"], 373810)

	def test_overtime_day(self):
		# 10h 근무(09:00~20:00, 휴게 60분) → regular 8h + overtime 2h
		sessions = [{"work_date": "2026-06-01", "start_time": "09:00", "end_time": "20:00", "break_minutes": 60}]
		out = estimate(sessions, hourly_rate=10000, contracted_weekly_hours=40)
		comp = {r["component"]: r["amount"] for r in out["earnings"]}
		self.assertEqual(comp["기본급"], 80000)          # 8h × 10,000
		self.assertEqual(comp["연장근로수당"], 30000)      # 2h × 10,000 × 1.5
		self.assertIn("weekly_overtime_limit", out["weekly_aggregate"])

	def test_holiday_day(self):
		sessions = [{"work_date": "2026-06-06", "start_time": "09:00", "end_time": "18:00",
			"break_minutes": 60, "is_holiday": True}]
		out = estimate(sessions, hourly_rate=10000, contracted_weekly_hours=40)
		comp = {r["component"]: r["amount"] for r in out["earnings"]}
		self.assertEqual(comp["휴일근로수당"], 120000)     # 8h × 10,000 × 1.5

	def test_not_perfect_attendance_no_weekly_holiday(self):
		out = estimate(BASIC_SESSIONS, hourly_rate=10000, contracted_weekly_hours=20,
			perfect_attendance=False)
		comp = {r["component"]: r["amount"] for r in out["earnings"]}
		self.assertNotIn("주휴수당", comp)

	def test_minimum_wage_flag(self):
		below = estimate(BASIC_SESSIONS, hourly_rate=9000, contracted_weekly_hours=20, minimum_wage=10030)
		ok = estimate(BASIC_SESSIONS, hourly_rate=10030, contracted_weekly_hours=20, minimum_wage=10030)
		self.assertTrue(below["below_minimum_wage"])
		self.assertFalse(ok["below_minimum_wage"])

	def test_extra_allowances(self):
		out = estimate(BASIC_SESSIONS, hourly_rate=10000, contracted_weekly_hours=20,
			extra_allowances=[{"component": "식대", "amount": 100000}])
		comp = {r["component"]: r["amount"] for r in out["earnings"]}
		self.assertEqual(comp["식대"], 100000)


class TestValidation(unittest.TestCase):
	def test_zero_rate_rejected(self):
		with self.assertRaises(ValueError):
			estimate(BASIC_SESSIONS, hourly_rate=0, contracted_weekly_hours=20)

	def test_missing_field_rejected(self):
		with self.assertRaises(ValueError):
			estimate([{"work_date": "2026-06-01", "start_time": "09:00"}], hourly_rate=10000, contracted_weekly_hours=20)

	def test_bad_time_rejected(self):
		with self.assertRaises(ValueError):
			estimate([{"work_date": "2026-06-01", "start_time": "구시", "end_time": "14:00"}], hourly_rate=10000, contracted_weekly_hours=20)

	def test_bad_json_rejected(self):
		with self.assertRaises(ValueError):
			estimate("{not json", hourly_rate=10000, contracted_weekly_hours=20)


if __name__ == "__main__":
	unittest.main()
