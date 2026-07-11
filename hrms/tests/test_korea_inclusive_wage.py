# -*- coding: utf-8 -*-
"""포괄임금 설계·역산 감사(inclusive_wage.py) 테스트 — 근기법 §56 가산수당 중심.

framework-free: inclusive_wage.py는 frappe import 없음.
hrms/__init__.py가 frappe를 import하므로 spec_from_file_location으로 직접 로드.
실행: python3 hrms/tests/test_korea_inclusive_wage.py
"""
import importlib.util
import pathlib
import unittest
from decimal import Decimal

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "hrms" / "regional" / "south_korea" / "inclusive_wage.py"

_spec = importlib.util.spec_from_file_location("inclusive_wage", _MODULE_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

design_inclusive_wage = _mod.design_inclusive_wage
audit_inclusive_wage = _mod.audit_inclusive_wage

MIN_WAGE_2026 = 10320


class TestDesignInclusiveWage(unittest.TestCase):
	def test_basic_ot_only_identity_and_floor_ok(self):
		# total 2,500,000 / (209 + 1.5*20=239) -> t=10,460.25... >= 10320
		r = design_inclusive_wage(2500000, 20, minimum_hourly_wage=MIN_WAGE_2026)
		self.assertEqual(r["base_pay"], 2186192)
		self.assertEqual(r["fixed_ot_pay"], 313808)
		self.assertEqual(r["night_pay"], 0)
		self.assertEqual(r["holiday_pay"], 0)
		self.assertEqual(r["total"], 2500000)
		self.assertTrue(r["legal_floor_ok"])
		self.assertEqual(r["warnings"], [])

	def test_identity_always_equals_input_total(self):
		# 임의 케이스에서도 base+ot+night+holiday == 입력 총액 (끝수는 기본급 흡수)
		r = design_inclusive_wage(
			3123456, 17, fixed_night_hours=6, fixed_holiday_hours=4, minimum_hourly_wage=MIN_WAGE_2026
		)
		self.assertEqual(
			r["base_pay"] + r["fixed_ot_pay"] + r["night_pay"] + r["holiday_pay"], 3123456
		)
		self.assertEqual(r["total"], 3123456)

	def test_with_night_hours(self):
		r = design_inclusive_wage(
			3000000, 20, fixed_night_hours=10, minimum_hourly_wage=MIN_WAGE_2026
		)
		self.assertEqual(r["base_pay"], 2569673)
		self.assertEqual(r["fixed_ot_pay"], 368852)
		self.assertEqual(r["night_pay"], 61475)
		self.assertEqual(r["holiday_pay"], 0)
		self.assertEqual(r["total"], 3000000)

	def test_with_holiday_hours(self):
		r = design_inclusive_wage(
			2500000, 10, fixed_holiday_hours=8, minimum_hourly_wage=MIN_WAGE_2026
		)
		self.assertEqual(r["base_pay"], 2213983)
		self.assertEqual(r["fixed_ot_pay"], 158898)
		self.assertEqual(r["night_pay"], 0)
		self.assertEqual(r["holiday_pay"], 127119)
		self.assertEqual(r["total"], 2500000)

	def test_rounding_remainder_absorbed_by_base_pay(self):
		# total 2,000,003 / (209+22.5=231.5) -> 끝수를 기본급이 흡수해도 검산 항등 유지
		r = design_inclusive_wage(2000003, 15, minimum_hourly_wage=MIN_WAGE_2026)
		self.assertEqual(r["fixed_ot_pay"], 194385)
		self.assertEqual(r["base_pay"], 1805618)
		self.assertEqual(r["base_pay"] + r["fixed_ot_pay"], 2000003)

	def test_below_minimum_wage_flags_not_ok_and_warns(self):
		r = design_inclusive_wage(1000000, 20, minimum_hourly_wage=MIN_WAGE_2026)
		self.assertFalse(r["legal_floor_ok"])
		self.assertTrue(any("최저임금" in w for w in r["warnings"]))

	def test_monthly_ot_hour_limit_exceeded_warns(self):
		# 고정연장 60h/월 > 주12h 한도(월 환산 약 52.14h, 근기법 §53①)
		r = design_inclusive_wage(2500000, 60, minimum_hourly_wage=MIN_WAGE_2026)
		self.assertTrue(any("12시간" in w or "한도" in w for w in r["warnings"]))

	def test_non_integer_total_monthly_rejected(self):
		"""총액은 원 단위(정수)여야 한다 — 절사해서 조용히 넘기지 않고 ValueError."""
		with self.assertRaises(ValueError):
			design_inclusive_wage(2500000.5, 20, minimum_hourly_wage=MIN_WAGE_2026)

	def test_zero_ot_night_holiday_reduces_to_209_division(self):
		r = design_inclusive_wage(2092000, 0, minimum_hourly_wage=MIN_WAGE_2026)
		self.assertEqual(r["base_pay"], 2092000)
		self.assertEqual(r["fixed_ot_pay"], 0)
		self.assertAlmostEqual(float(r["ordinary_hourly_wage"]), 2092000 / 209, places=2)


class TestAuditInclusiveWage(unittest.TestCase):
	def test_contract_matches_no_shortfall(self):
		# 기본급 2,156,880 -> t=10,320(=최저임금과 동일), 연장 20h 적정액 309,600
		r = audit_inclusive_wage(
			base_pay=2156880,
			fixed_ot_pay=309600,
			fixed_ot_hours=20,
			minimum_hourly_wage=MIN_WAGE_2026,
		)
		self.assertEqual(r["expected_ot_pay"], 309600)
		self.assertEqual(r["ot_shortfall"], 0)
		self.assertTrue(r["legal_floor_ok"])
		self.assertEqual(r["warnings"], [])

	def test_contract_underpays_ot_detected(self):
		r = audit_inclusive_wage(
			base_pay=2156880,
			fixed_ot_pay=250000,  # 적정 309,600보다 부족
			fixed_ot_hours=20,
			minimum_hourly_wage=MIN_WAGE_2026,
		)
		self.assertEqual(r["expected_ot_pay"], 309600)
		self.assertEqual(r["ot_shortfall"], 59600)
		self.assertTrue(any("부족" in w for w in r["warnings"]))

	def test_night_pay_shortfall_detected(self):
		r = audit_inclusive_wage(
			base_pay=3000000,
			fixed_ot_pay=430622,
			fixed_ot_hours=20,
			fixed_night_pay=50000,  # 적정 71,770보다 부족
			fixed_night_hours=10,
			minimum_hourly_wage=MIN_WAGE_2026,
		)
		self.assertEqual(r["expected_night_pay"], 71770)
		self.assertEqual(r["night_shortfall"], 21770)
		self.assertTrue(any("야간" in w and "부족" in w for w in r["warnings"]))

	def test_below_minimum_wage_detected(self):
		r = audit_inclusive_wage(
			base_pay=1000000,
			fixed_ot_pay=143541,
			fixed_ot_hours=20,
			minimum_hourly_wage=MIN_WAGE_2026,
		)
		self.assertFalse(r["legal_floor_ok"])
		self.assertTrue(any("최저임금" in w for w in r["warnings"]))

	def test_monthly_ot_hour_limit_exceeded_in_audit(self):
		r = audit_inclusive_wage(
			base_pay=2500000,
			fixed_ot_pay=1076555,
			fixed_ot_hours=60,
			minimum_hourly_wage=MIN_WAGE_2026,
		)
		self.assertFalse(r["overtime_limit_ok"])
		self.assertTrue(any("12시간" in w or "한도" in w for w in r["warnings"]))

	def test_negative_hours_rejected(self):
		with self.assertRaises(ValueError):
			audit_inclusive_wage(
				base_pay=2156880,
				fixed_ot_pay=309600,
				fixed_ot_hours=-1,
				minimum_hourly_wage=MIN_WAGE_2026,
			)

	def test_negative_pay_rejected(self):
		with self.assertRaises(ValueError):
			audit_inclusive_wage(
				base_pay=2156880,
				fixed_night_pay=-1,
				fixed_night_hours=10,
				minimum_hourly_wage=MIN_WAGE_2026,
			)

	def test_holiday_pay_shortfall_detected(self):
		# 기본급 2,500,000 -> t=11,961.72..., 휴일 8h 적정액 143,541
		r = audit_inclusive_wage(
			base_pay=2500000,
			fixed_holiday_pay=100000,  # 적정 143,541보다 부족
			fixed_holiday_hours=8,
			minimum_hourly_wage=MIN_WAGE_2026,
		)
		self.assertEqual(r["expected_holiday_pay"], 143541)
		self.assertEqual(r["holiday_shortfall"], 43541)
		self.assertTrue(any("휴일" in w and "부족" in w for w in r["warnings"]))


if __name__ == "__main__":
	unittest.main()
