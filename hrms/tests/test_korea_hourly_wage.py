# -*- coding: utf-8 -*-
"""시급제 급여 자동계산(hourly_wage.py) 테스트 — 주휴수당 §55·시행령 §30 중심.

framework-free: hourly_wage.py는 frappe import 없음.
hrms/__init__.py가 frappe를 import하므로 spec_from_file_location으로 직접 로드.
실행: python3 hrms/tests/test_korea_hourly_wage.py
"""
import importlib.util
import pathlib
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "hrms" / "regional" / "south_korea" / "hourly_wage.py"

_spec = importlib.util.spec_from_file_location("hourly_wage", _MODULE_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

weekly_holiday_hours = _mod.weekly_holiday_hours
weekly_holiday_allowance = _mod.weekly_holiday_allowance
monthly_weekly_holiday_allowance = _mod.monthly_weekly_holiday_allowance
is_below_minimum_wage = _mod.is_below_minimum_wage
compose_hourly_earnings = _mod.compose_hourly_earnings


class TestWeeklyHolidayHours(unittest.TestCase):
	def test_full_time_40h_is_8h(self):
		self.assertEqual(float(weekly_holiday_hours(40)), 8.0)

	def test_part_time_20h_is_4h(self):
		self.assertEqual(float(weekly_holiday_hours(20)), 4.0)

	def test_15h_is_3h(self):
		self.assertEqual(float(weekly_holiday_hours(15)), 3.0)

	def test_over_40h_capped_at_8h(self):
		# 연장근로는 소정근로에 미포함 → 48h여도 8h 상한
		self.assertEqual(float(weekly_holiday_hours(48)), 8.0)

	def test_zero_is_zero(self):
		self.assertEqual(float(weekly_holiday_hours(0)), 0.0)


class TestWeeklyHolidayAllowance(unittest.TestCase):
	def test_full_time(self):
		# 40h, 시급 10,000 → 8h × 10000 = 80,000
		self.assertEqual(weekly_holiday_allowance(contracted_weekly_hours=40, hourly_rate=10000), 80000)

	def test_part_time_20h(self):
		self.assertEqual(weekly_holiday_allowance(contracted_weekly_hours=20, hourly_rate=10000), 40000)

	def test_below_15h_no_allowance(self):
		# 주 14h → 주휴 발생 요건 미충족 (§18③)
		self.assertEqual(weekly_holiday_allowance(contracted_weekly_hours=14, hourly_rate=10000), 0)

	def test_exactly_15h_qualifies(self):
		self.assertEqual(weekly_holiday_allowance(contracted_weekly_hours=15, hourly_rate=10000), 30000)

	def test_not_perfect_attendance_no_allowance(self):
		# 개근하지 않으면 주휴수당 없음 (§55)
		self.assertEqual(
			weekly_holiday_allowance(contracted_weekly_hours=40, hourly_rate=10000, perfect_attendance=False),
			0,
		)

	def test_rounding_half_up(self):
		# 20h, 시급 10,030 → 4h × 10030 = 40,120
		self.assertEqual(weekly_holiday_allowance(contracted_weekly_hours=20, hourly_rate=10030), 40120)


class TestMonthlyWeeklyHolidayAllowance(unittest.TestCase):
	def test_full_time_monthly(self):
		# 주 80,000 × (365/12/7 ≈ 4.345238) = 347,619
		self.assertEqual(
			monthly_weekly_holiday_allowance(contracted_weekly_hours=40, hourly_rate=10000),
			347619,
		)

	def test_below_threshold_zero(self):
		self.assertEqual(
			monthly_weekly_holiday_allowance(contracted_weekly_hours=10, hourly_rate=10000),
			0,
		)

	def test_custom_weeks_per_month(self):
		# 주수 4.0 명시 → 80,000 × 4 = 320,000
		self.assertEqual(
			monthly_weekly_holiday_allowance(contracted_weekly_hours=40, hourly_rate=10000, weeks_per_month=4),
			320000,
		)


class TestMinimumWage(unittest.TestCase):
	def test_below(self):
		self.assertTrue(is_below_minimum_wage(9000, 10030))

	def test_equal_not_below(self):
		self.assertFalse(is_below_minimum_wage(10030, 10030))

	def test_above(self):
		self.assertFalse(is_below_minimum_wage(12000, 10030))


class TestComposeHourlyEarnings(unittest.TestCase):
	def test_basic_composition(self):
		result = compose_hourly_earnings(
			base_pay=1_000_000,
			weekly_holiday_pay=200_000,
			overtime_pay=150_000,
		)
		self.assertEqual(result["gross_pay"], 1_350_000)
		components = {line["component"]: line["amount"] for line in result["earnings"]}
		self.assertEqual(components["기본급"], 1_000_000)
		self.assertEqual(components["주휴수당"], 200_000)
		self.assertEqual(components["연장근로수당"], 150_000)

	def test_zero_lines_omitted(self):
		result = compose_hourly_earnings(base_pay=1_000_000)
		self.assertEqual(len(result["earnings"]), 1)
		self.assertEqual(result["gross_pay"], 1_000_000)

	def test_extra_allowances(self):
		result = compose_hourly_earnings(
			base_pay=1_000_000,
			extra_allowances=[{"component": "식대", "amount": 200_000}],
		)
		components = {line["component"]: line["amount"] for line in result["earnings"]}
		self.assertEqual(components["식대"], 200_000)
		self.assertEqual(result["gross_pay"], 1_200_000)


if __name__ == "__main__":
	unittest.main()
