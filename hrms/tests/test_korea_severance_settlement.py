# -*- coding: utf-8 -*-
"""퇴직정산 엔진 테스트 — 퇴직소득세·건보정산·통합 오케스트레이션.

framework-free: frappe import 없음. 개인 스킬(퇴직정산/건보정산, 읽기 전용)의
실무 수식을 검증하고, 소득세법 §48/§55② 경계값을 고정한다.

tdd: red→green
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
_MOD_PATH = ROOT / "hrms" / "regional" / "south_korea" / "severance_settlement.py"

spec = importlib.util.spec_from_file_location("severance_settlement", _MOD_PATH)
_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_mod)

calculate_severance_income_tax = _mod.calculate_severance_income_tax
reconcile_health_insurance_on_exit = _mod.reconcile_health_insurance_on_exit
settle_retirement = _mod.settle_retirement


def _d(s: str) -> dt.date:
    return dt.date.fromisoformat(s)


# ---------------------------------------------------------------------------
# calculate_severance_income_tax
# ---------------------------------------------------------------------------

class TestSeveranceIncomeTax(unittest.TestCase):
    def test_zero_when_pay_below_service_year_deduction(self):
        """퇴직소득금액이 근속연수공제(100만원×근속연수)에 미달 → 세액 0 (소득세법 §48②)."""
        result = calculate_severance_income_tax(severance_pay=500_000, service_years=1)
        self.assertEqual(result["income_tax"], 0)
        self.assertEqual(result["local_income_tax"], 0)
        self.assertEqual(result["total_tax"], 0)

    def test_zero_at_exact_service_year_deduction_boundary(self):
        """퇴직소득금액 == 근속연수공제(정확히 경계) → 과세표준 0, 세액 0."""
        result = calculate_severance_income_tax(severance_pay=1_000_000, service_years=1)
        self.assertEqual(result["income_tax"], 0)

    def test_low_income_is_not_forced_to_zero_when_taxable(self):
        """저소득이라도 근속연수공제를 초과하면 세액은 반드시 계산되어야 한다(0 강제 금지)."""
        # 3년 근속, 퇴직금 10,000,000원: 근속연수공제 = 100만*3 = 300만
        # 초과분 700만 -> 환산급여 = 700만 * 12 / 3 = 2,800만 (800만 초과)
        result = calculate_severance_income_tax(severance_pay=10_000_000, service_years=3)
        self.assertGreater(result["converted_wage"], 0)
        self.assertGreater(result["tax_base"], 0)
        self.assertGreater(result["income_tax"], 0)

    def test_service_years_five_or_fewer_boundary(self):
        """근속연수 5년 이하 구간: 공제 = 100만 × 근속연수."""
        result = calculate_severance_income_tax(severance_pay=50_000_000, service_years=5)
        self.assertEqual(result["service_year_deduction"], 5_000_000.0)

    def test_service_years_just_above_five_boundary(self):
        """근속연수 5년 초과(올림 적용 전 5.1년 -> 올림 6년) 구간 공제 확인."""
        result = calculate_severance_income_tax(severance_pay=50_000_000, service_years=5.1)
        # 5.1년 -> ceiling 6년 -> 공제 = 500만 + 200만*(6-5) = 700만
        self.assertEqual(result["service_years_rounded"], 6)
        self.assertEqual(result["service_year_deduction"], 7_000_000.0)

    def test_service_years_ten_boundary(self):
        """근속연수 정확히 10년 -> 공제 = 500만+200만*5 = 1,500만."""
        result = calculate_severance_income_tax(severance_pay=100_000_000, service_years=10)
        self.assertEqual(result["service_year_deduction"], 15_000_000.0)

    def test_service_years_just_above_ten_boundary(self):
        """근속연수 10년 초과(10.01년 -> 올림 11년) -> 공제 = 1,500만+250만*1 = 1,750만."""
        result = calculate_severance_income_tax(severance_pay=100_000_000, service_years=10.01)
        self.assertEqual(result["service_years_rounded"], 11)
        self.assertEqual(result["service_year_deduction"], 17_500_000.0)

    def test_service_years_twenty_boundary(self):
        """근속연수 정확히 20년 -> 공제 = 1,500만+250만*10 = 4,000만."""
        result = calculate_severance_income_tax(severance_pay=200_000_000, service_years=20)
        self.assertEqual(result["service_year_deduction"], 40_000_000.0)

    def test_service_years_just_above_twenty_boundary(self):
        """근속연수 20년 초과(20.01년 -> 올림 21년) -> 공제 = 4,000만+300만*1 = 4,300만."""
        result = calculate_severance_income_tax(severance_pay=200_000_000, service_years=20.01)
        self.assertEqual(result["service_years_rounded"], 21)
        self.assertEqual(result["service_year_deduction"], 43_000_000.0)

    def test_converted_wage_deduction_boundary_800man(self):
        """환산급여 정확히 800만원 -> 전액 공제 -> 과세표준 0."""
        # 근속 1년, 퇴직소득 900만: 공제 100만 -> 800만 (환산급여 = 800만*12/1=9600만... )
        # 환산급여가 정확히 800만이 되도록 역산: income_after=800만/12*1 근속1년
        # income_after_service_deduction * 12 / years = 8,000,000 => income_after = 8,000,000/12
        # severance_pay = income_after + service_deduction(1년=100만)
        income_after = 8_000_000 / 12
        pay = income_after + 1_000_000
        result = calculate_severance_income_tax(severance_pay=pay, service_years=1)
        self.assertAlmostEqual(result["converted_wage"], 8_000_000.0, delta=1.0)
        self.assertAlmostEqual(result["tax_base"], 0.0, delta=1.0)
        self.assertEqual(result["income_tax"], 0)

    def test_converted_wage_deduction_above_800man_uses_60_percent(self):
        """환산급여가 800만원 초과 시 초과분의 60%만 공제(40%는 과세표준에 남음)."""
        # 근속 1년, income_after = 환산급여(=income_after*12) 가 800만~7000만 구간에 들도록.
        income_after = 4_000_000  # 환산급여 = 4,800만 (800만 초과, 7000만 이하)
        pay = income_after + 1_000_000
        result = calculate_severance_income_tax(severance_pay=pay, service_years=1)
        converted_wage = result["converted_wage"]
        self.assertGreater(converted_wage, 8_000_000)
        expected_deduction = 8_000_000 + (converted_wage - 8_000_000) * 0.6
        self.assertAlmostEqual(result["converted_wage_deduction"], expected_deduction, delta=1.0)

    def test_income_tax_rounded_down_to_10_won(self):
        """소득세는 10원 단위 절사(올림 아님) — 원 단위 세액을 10원 배수로 강제 확인."""
        result = calculate_severance_income_tax(severance_pay=30_000_000, service_years=3)
        self.assertEqual(result["income_tax"] % 10, 0)
        self.assertEqual(result["local_income_tax"] % 10, 0)

    def test_local_income_tax_is_10_percent_of_income_tax(self):
        result = calculate_severance_income_tax(severance_pay=30_000_000, service_years=3)
        # 지방소득세는 소득세×10%를 10원 절사한 값이어야 하며, 절사 오차는 10원 미만.
        expected_before_floor = result["income_tax"] * 0.1
        self.assertLessEqual(abs(result["local_income_tax"] - (expected_before_floor // 10) * 10), 0.01)

    def test_negative_severance_pay_rejected(self):
        with self.assertRaises(ValueError):
            calculate_severance_income_tax(severance_pay=-1, service_years=1)

    def test_zero_or_negative_service_years_rejected(self):
        with self.assertRaises(ValueError):
            calculate_severance_income_tax(severance_pay=1_000_000, service_years=0)


# ---------------------------------------------------------------------------
# reconcile_health_insurance_on_exit
# ---------------------------------------------------------------------------

class TestHealthInsuranceReconciliation(unittest.TestCase):
    def test_basic_reconciliation_matches_skill_example(self):
        """개인 스킬 예시: 건보 산출과 기납부 차액 = 정산액(추가납부 양수)."""
        # 월평균보수 2,000,000원 가정, 6개월(1일 입사, 중도입사 아님)
        result = reconcile_health_insurance_on_exit(
            monthly_remuneration=[2_000_000] * 6,
            paid_health_total=0,
            paid_longterm_care_total=0,
            mid_month_hire=False,
        )
        self.assertEqual(result["calc_months"], 6)
        self.assertEqual(result["paid_months"], 6)
        # 건강보험 월액 = ROUNDDOWN(2,000,000*0.03595, -1) = ROUNDDOWN(71,900, -1) = 71,900
        self.assertEqual(result["monthly_health_insurance"], 71_900)
        self.assertEqual(result["determined_health_insurance"], 71_900 * 6)
        self.assertEqual(result["health_insurance_settlement"], 71_900 * 6)

    def test_mid_month_hire_reduces_paid_months(self):
        """중도입사(1일 아님) -> 납부월수 = 산정월수 - 1 (입사월 미납)."""
        result = reconcile_health_insurance_on_exit(
            monthly_remuneration=[2_000_000] * 4,
            mid_month_hire=True,
        )
        self.assertEqual(result["calc_months"], 4)
        self.assertEqual(result["paid_months"], 3)
        self.assertEqual(result["determined_health_insurance"], result["monthly_health_insurance"] * 3)

    def test_refund_when_paid_exceeds_determined(self):
        """기납부가 확정보험료보다 크면 정산액은 음수(환급)."""
        result = reconcile_health_insurance_on_exit(
            monthly_remuneration=[1_000_000] * 3,
            paid_health_total=999_999_999,
            paid_longterm_care_total=999_999_999,
        )
        self.assertLess(result["health_insurance_settlement"], 0)
        self.assertLess(result["longterm_care_settlement"], 0)

    def test_no_settlement_when_paid_equals_determined(self):
        """산정=납부(기납부가 확정보험료와 정확히 일치) -> 정산액 0."""
        probe = reconcile_health_insurance_on_exit(monthly_remuneration=[2_000_000] * 6)
        result = reconcile_health_insurance_on_exit(
            monthly_remuneration=[2_000_000] * 6,
            paid_health_total=probe["determined_health_insurance"],
            paid_longterm_care_total=probe["determined_longterm_care"],
        )
        self.assertEqual(result["health_insurance_settlement"], 0)
        self.assertEqual(result["longterm_care_settlement"], 0)

    def test_longterm_care_uses_2026_conversion_rate(self):
        """장기요양 = 확정 건강보험료(10원 절사) × 13.1405%(2026 환산율), 10원 절사."""
        result = reconcile_health_insurance_on_exit(monthly_remuneration=[2_000_000] * 1)
        health = result["monthly_health_insurance"]
        expected_longterm = int((health * (0.009448 / 0.0719)) // 10) * 10
        self.assertEqual(result["monthly_longterm_care"], expected_longterm)

    def test_empty_monthly_remuneration_rejected(self):
        with self.assertRaises(ValueError):
            reconcile_health_insurance_on_exit(monthly_remuneration=[])


# ---------------------------------------------------------------------------
# settle_retirement (통합 오케스트레이션)
# ---------------------------------------------------------------------------

class TestSettleRetirement(unittest.TestCase):
    def test_integration_produces_all_sections(self):
        result = settle_retirement(
            hire_date=_d("2020-01-01"),
            severance_date=_d("2025-01-01"),
            average_wage_per_day=100_000,
            monthly_base_salary=2_090_000,  # 209h * 10,000
            ordinary_wage_per_day=None,
            unused_leave_days=5,
            monthly_remuneration_for_health=[2_000_000] * 12,
            paid_health_total=71_900 * 11,
            paid_longterm_care_total=0,
            mid_month_hire=False,
        )
        self.assertIn("severance_pay", result)
        self.assertIn("unused_leave_allowance", result)
        self.assertIn("severance_income_tax", result)
        self.assertIn("health_insurance_reconciliation", result)
        self.assertIn("payout_summary", result)

        self.assertTrue(result["severance_pay"]["qualified_for_severance"])
        self.assertIsNotNone(result["severance_income_tax"])
        self.assertIsNotNone(result["health_insurance_reconciliation"])

        # 미사용연차수당 = 기본급/209*8*5 = 10,000*8*5 = 400,000
        self.assertEqual(result["unused_leave_allowance"], 400_000)

        summary = result["payout_summary"]
        self.assertEqual(
            summary["net_severance_payout"],
            summary["severance_pay_amount"] - summary["severance_income_tax"] - summary["severance_local_income_tax"],
        )

    def test_under_one_year_service_has_no_severance_tax(self):
        """1년 미만 재직 -> 퇴직금 0 -> 퇴직소득세 계산 생략(None)."""
        result = settle_retirement(
            hire_date=_d("2024-06-01"),
            severance_date=_d("2024-09-01"),
            average_wage_per_day=100_000,
            monthly_base_salary=2_090_000,
        )
        self.assertFalse(result["severance_pay"]["qualified_for_severance"])
        self.assertIsNone(result["severance_income_tax"])
        self.assertEqual(result["payout_summary"]["severance_income_tax"], 0)

    def test_no_health_reconciliation_when_not_requested(self):
        result = settle_retirement(
            hire_date=_d("2020-01-01"),
            severance_date=_d("2025-01-01"),
            average_wage_per_day=100_000,
            monthly_base_salary=2_090_000,
        )
        self.assertIsNone(result["health_insurance_reconciliation"])
        self.assertEqual(result["payout_summary"]["health_insurance_settlement"], 0)


if __name__ == "__main__":
    unittest.main()
