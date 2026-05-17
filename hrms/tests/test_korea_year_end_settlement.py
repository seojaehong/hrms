"""
연말정산 계산기 단위 테스트 (소득세법 기반, 2026년 귀속분)

Frappe 프레임워크 의존성 없이 순수 계산 검증.
실행: python -m unittest hrms.tests.test_korea_year_end_settlement

소득세법 참조:
- 47조의2: 근로소득공제
- 47조: 인적공제 (기본공제 1인 150만원)
- 51조: 특별소득공제
- 55조: 기본세율
- 59조: 세액공제
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


def _load_module():
    """Frappe 없이 모듈 직접 로드."""
    module_path = Path(__file__).resolve().parent.parent / "regional" / "south_korea" / "year_end_settlement.py"
    spec = importlib.util.spec_from_file_location("year_end_settlement", module_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_mod = _load_module()
calculate_year_end_settlement = _mod.calculate_year_end_settlement


class TestEarnedIncomeDeduction(unittest.TestCase):
    """근로소득공제 구간별 테스트 (소득세법 47조의2)."""

    def _deduction(self, salary: float) -> float:
        r = calculate_year_end_settlement(
            employee="X", tax_year=2025, total_salary=salary, monthly_paid_income_tax=0
        )
        return r["earned_income_deduction"]

    def test_bracket_1_below_5m(self):
        # 500만 이하: 70%
        # 총급여 300만 → 공제 300만×70% = 210만
        self.assertAlmostEqual(self._deduction(3_000_000), 2_100_000, delta=1.0)

    def test_bracket_2_5m_to_15m(self):
        # 총급여 1,000만 → 350만 + (1000만-500만)×40% = 350만+200만 = 550만
        self.assertAlmostEqual(self._deduction(10_000_000), 5_500_000, delta=1.0)

    def test_bracket_3_15m_to_45m(self):
        # 총급여 3,000만 → 750만 + (3000만-1500만)×15% = 750만+225만 = 975만
        self.assertAlmostEqual(self._deduction(30_000_000), 9_750_000, delta=1.0)

    def test_bracket_4_45m_to_100m(self):
        # 총급여 7,000만 → 1200만 + (7000만-4500만)×5% = 1200만+125만 = 1325만
        self.assertAlmostEqual(self._deduction(70_000_000), 13_250_000, delta=1.0)

    def test_bracket_5_over_100m(self):
        # 총급여 1.5억 → 1475만 + (1.5억-1억)×2% = 1475만+100만 = 1575만
        self.assertAlmostEqual(self._deduction(150_000_000), 15_750_000, delta=1.0)

    def test_cap_at_20m(self):
        # 총급여 매우 클 때 → 한도 2,000만원
        deduction = self._deduction(1_000_000_000)
        self.assertAlmostEqual(deduction, 20_000_000, delta=1.0)


class TestBaseTaxRate(unittest.TestCase):
    """
    기본세율 구간별 테스트 (소득세법 55조).

    누진공제액 = boundary × (new_rate - prev_rate) + prev_누진공제
    - 14M 경계: 14M×(0.15-0.06)=1,260,000
    - 50M 경계: 1,260,000+50M×(0.24-0.15)=5,760,000
    - 88M 경계: 5,760,000+88M×(0.35-0.24)=15,440,000
    """

    def _tax(self, tax_base: float) -> float:
        return _mod._calc_income_tax(tax_base)

    def test_continuity_at_14m_boundary(self):
        """14,000,000 경계에서 양 구간 세액 일치 확인."""
        # 6% 구간: 14,000,000 × 0.06 - 0 = 840,000
        # 15% 구간: 14,000,000 × 0.15 - 1,260,000 = 840,000
        self.assertAlmostEqual(self._tax(14_000_000), 840_000, delta=1.0)

    def test_continuity_at_50m_boundary(self):
        """50,000,000 경계에서 양 구간 세액 일치 확인."""
        # 15% 구간: 50,000,000 × 0.15 - 1,260,000 = 6,240,000
        # 24% 구간: 50,000,000 × 0.24 - 5,760,000 = 6,240,000
        self.assertAlmostEqual(self._tax(50_000_000), 6_240_000, delta=1.0)

    def test_continuity_at_88m_boundary(self):
        """88,000,000 경계에서 양 구간 세액 일치 확인."""
        # 24% 구간: 88,000,000 × 0.24 - 5,760,000 = 15,360,000
        # 35% 구간: 88,000,000 × 0.35 - 15,440,000 = 15,360,000
        self.assertAlmostEqual(self._tax(88_000_000), 15_360_000, delta=1.0)

    def test_bracket_6pct(self):
        # 과세표준 1,000만 → 1,000만×6% - 0 = 600,000
        self.assertAlmostEqual(self._tax(10_000_000), 600_000, delta=1.0)

    def test_bracket_15pct(self):
        # 과세표준 3,000만 → 3,000만×15% - 1,260,000 = 3,240,000
        # 직접 계산: 14M×6% + 16M×15% = 840,000 + 2,400,000 = 3,240,000
        self.assertAlmostEqual(self._tax(30_000_000), 3_240_000, delta=1.0)

    def test_bracket_24pct(self):
        # 과세표준 7,000만 → 7,000만×24% - 5,760,000 = 11,040,000
        # 직접 계산: 14M×6% + 36M×15% + 20M×24% = 840,000+5,400,000+4,800,000 = 11,040,000
        self.assertAlmostEqual(self._tax(70_000_000), 11_040_000, delta=1.0)

    def test_bracket_35pct(self):
        # 과세표준 1.2억 → 1.2억×35% - 15,440,000 = 42,000,000-15,440,000 = 26,560,000
        self.assertAlmostEqual(self._tax(120_000_000), 26_560_000, delta=1.0)

    def test_zero_tax_base(self):
        self.assertAlmostEqual(self._tax(0), 0, delta=0.01)


class TestCase1_30M_Dep1_Insurance264(unittest.TestCase):
    """
    케이스 1: 연봉 3,000만원, 부양 1인(본인), 4대보험 264만원.

    단계별 계산 (소득세법 55조 누진공제 적용):
    총급여:       30,000,000
    근로소득공제: 7,500,000 + (30,000,000-15,000,000)×15% = 9,750,000
    근로소득금액: 20,250,000
    인적공제:     1인×150만 = 1,500,000
    특별소득공제: 4대보험 2,640,000
    과세표준:     20,250,000 - 1,500,000 - 2,640,000 = 16,110,000
    산출세액:     16,110,000×0.15 - 1,260,000 = 2,416,500 - 1,260,000 = 1,156,500
                  (직접 계산: 14M×6% + 2.11M×15% = 840,000+316,500 = 1,156,500)
    근로소득세액공제: 산출세액 1,156,500 < 130만 → 1,156,500×55% = 636,075
                     한도(총급여 3,000만 ≤ 3,300만): 74만 → min(636,075, 740,000) = 636,075
    총세액공제:   636,075
    결정세액:     1,156,500 - 636,075 = 520,425
    """

    def setUp(self):
        self.result = calculate_year_end_settlement(
            employee="EMP001",
            tax_year=2025,
            total_salary=30_000_000,
            monthly_paid_income_tax=350_000,
            dependents=1,
            insurance_premiums=2_640_000,
        )

    def test_contract_type(self):
        self.assertEqual(self.result["contract_type"], "korea_year_end_settlement_v1")

    def test_tax_year(self):
        self.assertEqual(self.result["tax_year"], 2025)

    def test_earned_income_deduction(self):
        # 9,750,000
        self.assertAlmostEqual(self.result["earned_income_deduction"], 9_750_000, delta=1.0)

    def test_earned_income(self):
        # 30,000,000 - 9,750,000 = 20,250,000
        self.assertAlmostEqual(self.result["earned_income"], 20_250_000, delta=1.0)

    def test_personal_deduction(self):
        # 1 × 1,500,000 = 1,500,000
        self.assertAlmostEqual(self.result["personal_deduction"], 1_500_000, delta=1.0)

    def test_special_income_deduction(self):
        # 4대보험 2,640,000 (신용카드 0)
        self.assertAlmostEqual(self.result["special_income_deduction"], 2_640_000, delta=1.0)

    def test_tax_base(self):
        # 20,250,000 - 1,500,000 - 2,640,000 = 16,110,000
        self.assertAlmostEqual(self.result["tax_base"], 16_110_000, delta=1.0)

    def test_calculated_tax(self):
        # 16,110,000 × 0.15 - 1,260,000 = 1,156,500
        self.assertAlmostEqual(self.result["calculated_tax"], 1_156_500, delta=1.0)

    def test_tax_credits(self):
        # 산출세액 115.65만 < 130만 → 55% = 636,075
        # 한도(총급여 3,000만 ≤ 3,300만): 74만 → 636,075 (한도 미달)
        self.assertAlmostEqual(self.result["tax_credits"], 636_075, delta=1.0)

    def test_determined_tax(self):
        # 1,156,500 - 636,075 = 520,425
        self.assertAlmostEqual(self.result["determined_tax"], 520_425, delta=1.0)

    def test_refund_or_pay_direction(self):
        # 기납부 35만 < 결정세액 52.04만 → 추징 (음수)
        self.assertLess(self.result["refund_or_pay"], 0)

    def test_refund_or_pay_amount(self):
        # 350,000 - 520,425 = -170,425
        self.assertAlmostEqual(self.result["refund_or_pay"], -170_425, delta=1.0)

    def test_local_tax_settlement(self):
        # -170,425 × 10% = -17,042.50
        self.assertAlmostEqual(self.result["local_tax_settlement"], -17_042.5, delta=1.0)


class TestCase2_50M_Dep2_Child1_Medical500(unittest.TestCase):
    """
    케이스 2: 연봉 5,000만원, 부양 2인(본인+1), 배우자, 자녀 1명, 의료비 50만원.

    단계별 계산 (소득세법 55조 누진공제 적용):
    총급여:       50,000,000
    근로소득공제: 12,000,000 + (50,000,000-45,000,000)×5% = 12,250,000
    근로소득금액: 37,750,000
    인적공제:     (2+1)×150만 = 4,500,000  # 부양2 + 배우자1
    특별소득공제: 0 (보험료/주택이자 없음)
    과세표준:     37,750,000 - 4,500,000 = 33,250,000
    산출세액:     33,250,000×0.15 - 1,260,000 = 4,987,500 - 1,260,000 = 3,727,500
                  (직접: 14M×6% + 19.25M×15% = 840,000+2,887,500 = 3,727,500)
    근로소득세액공제: min(715,000 + (3,727,500-1,300,000)×30%, 660,000)
                  = min(715,000+728,250, 660,000) = min(1,443,250, 660,000) = 660,000
    자녀세액공제: 1명 → 150,000
    의료비세액공제: 50,000,000×3%=1,500,000 > 500,000 → 초과분 없음 → 0
    총세액공제:   660,000 + 150,000 = 810,000
    결정세액:     3,727,500 - 810,000 = 2,917,500
    기납부: 2,000,000 < 결정세액 → 추징
    """

    def setUp(self):
        self.result = calculate_year_end_settlement(
            employee="EMP002",
            tax_year=2025,
            total_salary=50_000_000,
            monthly_paid_income_tax=2_000_000,
            dependents=2,
            children_under_8=1,
            spouse=True,
            medical_expenses=500_000,
        )

    def test_earned_income_deduction(self):
        # 12,000,000 + (50,000,000-45,000,000)×0.05 = 12,250,000
        self.assertAlmostEqual(self.result["earned_income_deduction"], 12_250_000, delta=1.0)

    def test_personal_deduction(self):
        # (2+1) × 1,500,000 = 4,500,000
        self.assertAlmostEqual(self.result["personal_deduction"], 4_500_000, delta=1.0)

    def test_tax_base(self):
        # 37,750,000 - 4,500,000 - 0 = 33,250,000
        self.assertAlmostEqual(self.result["tax_base"], 33_250_000, delta=1.0)

    def test_calculated_tax(self):
        # 33,250,000 × 0.15 - 1,260,000 = 3,727,500
        self.assertAlmostEqual(self.result["calculated_tax"], 3_727_500, delta=1.0)

    def test_tax_credits(self):
        # 근로소득세액공제 66만 + 자녀1 15만 = 81만
        self.assertAlmostEqual(self.result["tax_credits"], 810_000, delta=1.0)

    def test_determined_tax(self):
        # 3,727,500 - 810,000 = 2,917,500
        self.assertAlmostEqual(self.result["determined_tax"], 2_917_500, delta=1.0)

    def test_medical_expense_below_threshold(self):
        # 의료비 50만 < 총급여×3%=150만 → 세액공제 없음 → 결정세액에 영향 없음
        # 의료비 없는 결과와 동일해야 함
        result_no_medical = calculate_year_end_settlement(
            employee="EMP002",
            tax_year=2025,
            total_salary=50_000_000,
            monthly_paid_income_tax=2_000_000,
            dependents=2,
            children_under_8=1,
            spouse=True,
        )
        self.assertAlmostEqual(
            self.result["determined_tax"], result_no_medical["determined_tax"], delta=1.0
        )

    def test_refund_or_pay_direction(self):
        # 기납부 200만 < 결정세액 291.75만 → 추징 (음수)
        self.assertLess(self.result["refund_or_pay"], 0)

    def test_refund_or_pay_amount(self):
        # 2,000,000 - 2,917,500 = -917,500
        self.assertAlmostEqual(self.result["refund_or_pay"], -917_500, delta=1.0)


class TestCase3_80M_MultipleDeductions(unittest.TestCase):
    """
    케이스 3: 연봉 8,000만원 + 다양한 공제 → 환급.

    단계별 계산 (소득세법 55조 누진공제 적용):
    총급여:       80,000,000
    근로소득공제: 12,000,000 + (80,000,000-45,000,000)×5% = 13,750,000
    근로소득금액: 66,250,000
    인적공제:     (1+1)×150만 = 3,000,000
    특별소득공제: 보험료 350만 + 주택이자 500만 + 신용카드 0
                  신용카드: 2,000만 - 8,000만×25%=0
                  = 8,500,000
    과세표준:     66,250,000 - 3,000,000 - 8,500,000 = 54,750,000
    산출세액:     54,750,000×0.24 - 5,760,000 = 13,140,000-5,760,000 = 7,380,000
                  (직접: 14M×6%+36M×15%+4.75M×24% = 840,000+5,400,000+1,140,000 = 7,380,000)
    근로소득세액공제: min(715,000+(7,380,000-1,300,000)×30%, 500,000)
                   = min(715,000+1,824,000, 500,000) = 500,000
    자녀세액공제: 2명 → 350,000
    연금저축공제: min(400만,600만)×12% = 480,000
    의료비공제:   200만-8,000만×3%=200만-240만=음수→0
    교육비공제:   300만×15% = 450,000
    기부금공제:   50만×15% = 75,000
    총세액공제:   500,000+350,000+480,000+0+450,000+75,000 = 1,855,000
    결정세액:     7,380,000-1,855,000 = 5,525,000
    기납부: 8,000,000 > 결정세액 → 환급
    환급액: 8,000,000-5,525,000 = 2,475,000
    """

    def setUp(self):
        self.result = calculate_year_end_settlement(
            employee="EMP003",
            tax_year=2025,
            total_salary=80_000_000,
            monthly_paid_income_tax=8_000_000,
            dependents=1,
            children_under_8=2,
            spouse=True,
            insurance_premiums=3_500_000,
            medical_expenses=2_000_000,
            education_expenses=3_000_000,
            housing_loan_interest=5_000_000,
            pension_savings=4_000_000,
            donation=500_000,
            credit_card_usage=20_000_000,
        )

    def test_earned_income_deduction(self):
        # 12,000,000 + (80,000,000-45,000,000)×0.05 = 13,750,000
        self.assertAlmostEqual(self.result["earned_income_deduction"], 13_750_000, delta=1.0)

    def test_personal_deduction(self):
        # (1+1)×150만 = 300만
        self.assertAlmostEqual(self.result["personal_deduction"], 3_000_000, delta=1.0)

    def test_credit_card_deduction_zero(self):
        # 신용카드 2천만, 총급여×25% = 2천만 → 초과분 0 → 공제 0
        # special_income_deduction = 350만+500만+0 = 850만
        self.assertAlmostEqual(self.result["special_income_deduction"], 8_500_000, delta=1.0)

    def test_tax_base(self):
        # 66,250,000 - 3,000,000 - 8,500,000 = 54,750,000
        self.assertAlmostEqual(self.result["tax_base"], 54_750_000, delta=1.0)

    def test_calculated_tax(self):
        # 54,750,000 × 0.24 - 5,760,000 = 7,380,000
        self.assertAlmostEqual(self.result["calculated_tax"], 7_380_000, delta=1.0)

    def test_tax_credits_breakdown(self):
        # 근로50만+자녀35만+연금48만+의료0+교육45만+기부7.5만 = 185.5만
        self.assertAlmostEqual(self.result["tax_credits"], 1_855_000, delta=1.0)

    def test_determined_tax(self):
        # 7,380,000 - 1,855,000 = 5,525,000
        self.assertAlmostEqual(self.result["determined_tax"], 5_525_000, delta=1.0)

    def test_refund_or_pay_direction(self):
        # 기납부 800만 > 결정세액 552.5만 → 환급 (양수)
        self.assertGreater(self.result["refund_or_pay"], 0)

    def test_refund_or_pay_amount(self):
        # 8,000,000 - 5,525,000 = 2,475,000
        self.assertAlmostEqual(self.result["refund_or_pay"], 2_475_000, delta=1.0)

    def test_local_tax_settlement_positive(self):
        # 환급이므로 지방소득세도 환급 (양수)
        self.assertGreater(self.result["local_tax_settlement"], 0)
        # 2,475,000 × 10% = 247,500
        self.assertAlmostEqual(self.result["local_tax_settlement"], 247_500, delta=1.0)


class TestCase4_100M_Dep1_PossibleCharge(unittest.TestCase):
    """
    케이스 4: 연봉 1억원, 부양 1인(본인) → 추징.

    단계별 계산 (소득세법 55조 누진공제 적용):
    총급여:       100,000,000
    근로소득공제: 14,750,000 (1억 경계 = 1475만 + 0)
    근로소득금액: 85,250,000
    인적공제:     1×150만 = 1,500,000
    특별소득공제: 0
    과세표준:     85,250,000 - 1,500,000 = 83,750,000
    산출세액:     83,750,000×0.24 - 5,760,000 = 20,100,000-5,760,000 = 14,340,000
                  (직접: 14M×6%+36M×15%+33.75M×24% = 840,000+5,400,000+8,100,000 = 14,340,000)
    근로소득세액공제: min(715,000+(14,340,000-1,300,000)×30%, 500,000)=500,000
    총세액공제:   500,000
    결정세액:     14,340,000 - 500,000 = 13,840,000
    기납부: 12,000,000 < 결정세액 → 추징
    추징액: 12,000,000-13,840,000 = -1,840,000
    """

    def setUp(self):
        self.result = calculate_year_end_settlement(
            employee="EMP004",
            tax_year=2025,
            total_salary=100_000_000,
            monthly_paid_income_tax=12_000_000,
            dependents=1,
        )

    def test_earned_income_deduction(self):
        # 100,000,000: 1475만 + (1억-1억)×2% = 14,750,000
        self.assertAlmostEqual(self.result["earned_income_deduction"], 14_750_000, delta=1.0)

    def test_tax_base(self):
        # 85,250,000 - 1,500,000 = 83,750,000
        self.assertAlmostEqual(self.result["tax_base"], 83_750_000, delta=1.0)

    def test_calculated_tax(self):
        # 83,750,000 × 0.24 - 5,760,000 = 14,340,000
        self.assertAlmostEqual(self.result["calculated_tax"], 14_340_000, delta=1.0)

    def test_earned_income_tax_credit_cap_high(self):
        # 총급여 1억 > 7,000만 → 한도 50만원 적용
        # 자녀/보험료/기부금 등 없음 → 세액공제 = 50만원
        self.assertAlmostEqual(self.result["tax_credits"], 500_000, delta=1.0)

    def test_determined_tax(self):
        # 14,340,000 - 500,000 = 13,840,000
        self.assertAlmostEqual(self.result["determined_tax"], 13_840_000, delta=1.0)

    def test_refund_or_pay_is_negative(self):
        # 추징: 음수
        self.assertLess(self.result["refund_or_pay"], 0)

    def test_refund_or_pay_amount(self):
        # 12,000,000 - 13,840,000 = -1,840,000
        self.assertAlmostEqual(self.result["refund_or_pay"], -1_840_000, delta=1.0)

    def test_local_tax_settlement(self):
        # -1,840,000 × 10% = -184,000
        self.assertAlmostEqual(self.result["local_tax_settlement"], -184_000, delta=1.0)


class TestEdgeCases(unittest.TestCase):
    """경계 조건 테스트."""

    def test_zero_salary_all_zeros(self):
        """총급여 0 → 모든 결과 0."""
        result = calculate_year_end_settlement(
            employee="EMP000",
            tax_year=2025,
            total_salary=0,
            monthly_paid_income_tax=0,
            dependents=1,
        )
        self.assertEqual(result["contract_type"], "korea_year_end_settlement_v1")
        self.assertAlmostEqual(result["earned_income_deduction"], 0, delta=0.01)
        self.assertAlmostEqual(result["tax_base"], 0, delta=0.01)
        self.assertAlmostEqual(result["calculated_tax"], 0, delta=0.01)
        self.assertAlmostEqual(result["determined_tax"], 0, delta=0.01)
        self.assertAlmostEqual(result["refund_or_pay"], 0, delta=0.01)
        self.assertAlmostEqual(result["local_tax_settlement"], 0, delta=0.01)

    def test_tax_base_cannot_be_negative(self):
        """과세표준 최소값 = 0 (공제 합계가 근로소득금액 초과해도 음수 불가)."""
        result = calculate_year_end_settlement(
            employee="EMPX",
            tax_year=2025,
            total_salary=5_000_000,   # 소액
            monthly_paid_income_tax=0,
            dependents=10,            # 인적공제 1500만 → 과세표준 음수 불가
        )
        self.assertGreaterEqual(result["tax_base"], 0)

    def test_determined_tax_cannot_be_negative(self):
        """결정세액 최소값 = 0 (세액공제 합계가 산출세액 초과해도 음수 불가)."""
        result = calculate_year_end_settlement(
            employee="EMPX",
            tax_year=2025,
            total_salary=10_000_000,
            monthly_paid_income_tax=0,
            dependents=1,
            pension_savings=600_000_000,  # 극단적으로 큰 연금저축
            donation=100_000_000,
        )
        self.assertGreaterEqual(result["determined_tax"], 0)

    def test_full_refund_when_overpaid(self):
        """기납부세액 > 결정세액 → 환급 (양수)."""
        result = calculate_year_end_settlement(
            employee="EMPX",
            tax_year=2025,
            total_salary=30_000_000,
            monthly_paid_income_tax=5_000_000,  # 과납
            dependents=1,
        )
        self.assertGreater(result["refund_or_pay"], 0)

    def test_spouse_adds_to_personal_deduction(self):
        """배우자 공제가 인적공제에 추가되는지 확인."""
        without_spouse = calculate_year_end_settlement(
            employee="EMPX", tax_year=2025,
            total_salary=40_000_000, monthly_paid_income_tax=0,
            dependents=1, spouse=False
        )
        with_spouse = calculate_year_end_settlement(
            employee="EMPX", tax_year=2025,
            total_salary=40_000_000, monthly_paid_income_tax=0,
            dependents=1, spouse=True
        )
        diff = with_spouse["personal_deduction"] - without_spouse["personal_deduction"]
        self.assertAlmostEqual(diff, 1_500_000, delta=1.0)

    def test_housing_loan_interest_cap(self):
        """주택자금 이자상환액 한도(2,000만원) 검증."""
        result_capped = calculate_year_end_settlement(
            employee="EMPX", tax_year=2025,
            total_salary=100_000_000, monthly_paid_income_tax=0,
            housing_loan_interest=30_000_000,  # 3천만 → 한도 2천만 적용
        )
        result_max = calculate_year_end_settlement(
            employee="EMPX", tax_year=2025,
            total_salary=100_000_000, monthly_paid_income_tax=0,
            housing_loan_interest=20_000_000,  # 정확히 한도
        )
        self.assertAlmostEqual(
            result_capped["special_income_deduction"],
            result_max["special_income_deduction"],
            delta=1.0
        )

    def test_credit_card_threshold_not_exceeded(self):
        """신용카드 사용액이 총급여 25% 미만 → 소득공제 0."""
        result = calculate_year_end_settlement(
            employee="EMPX", tax_year=2025,
            total_salary=40_000_000, monthly_paid_income_tax=0,
            credit_card_usage=9_000_000,  # 4천만×25% = 1천만 > 9백만
        )
        # 특별소득공제 0 (보험료/주택이자 없음)
        self.assertAlmostEqual(result["special_income_deduction"], 0, delta=1.0)

    def test_pension_savings_rate_low_salary(self):
        """총급여 5,500만 이하 → 연금저축 세액공제율 15%."""
        result = calculate_year_end_settlement(
            employee="EMPX", tax_year=2025,
            total_salary=55_000_000, monthly_paid_income_tax=0,
            dependents=1, pension_savings=1_000_000,
        )
        # 100만×15% = 15만 기여
        result_no_pension = calculate_year_end_settlement(
            employee="EMPX", tax_year=2025,
            total_salary=55_000_000, monthly_paid_income_tax=0,
            dependents=1,
        )
        diff = result["tax_credits"] - result_no_pension["tax_credits"]
        self.assertAlmostEqual(diff, 150_000, delta=1.0)

    def test_pension_savings_rate_high_salary(self):
        """총급여 5,500만 초과 → 연금저축 세액공제율 12%."""
        result = calculate_year_end_settlement(
            employee="EMPX", tax_year=2025,
            total_salary=56_000_000, monthly_paid_income_tax=0,
            dependents=1, pension_savings=1_000_000,
        )
        result_no_pension = calculate_year_end_settlement(
            employee="EMPX", tax_year=2025,
            total_salary=56_000_000, monthly_paid_income_tax=0,
            dependents=1,
        )
        diff = result["tax_credits"] - result_no_pension["tax_credits"]
        self.assertAlmostEqual(diff, 120_000, delta=1.0)

    def test_child_tax_credit_3_children(self):
        """자녀 3명 세액공제: 35만 + 30만 = 65만."""
        result = calculate_year_end_settlement(
            employee="EMPX", tax_year=2025,
            total_salary=60_000_000, monthly_paid_income_tax=0,
            children_under_8=3,
        )
        result_no_child = calculate_year_end_settlement(
            employee="EMPX", tax_year=2025,
            total_salary=60_000_000, monthly_paid_income_tax=0,
        )
        diff = result["tax_credits"] - result_no_child["tax_credits"]
        self.assertAlmostEqual(diff, 650_000, delta=1.0)

    def test_local_tax_is_10pct_of_income_tax_settlement(self):
        """지방소득세 연말정산 = 소득세 환급/추징의 10%."""
        result = calculate_year_end_settlement(
            employee="EMPX", tax_year=2025,
            total_salary=50_000_000, monthly_paid_income_tax=3_000_000,
            dependents=1,
        )
        expected_local = result["refund_or_pay"] * 0.10
        self.assertAlmostEqual(result["local_tax_settlement"], expected_local, delta=0.01)

    def test_output_keys_complete(self):
        """반환 딕셔너리에 명세된 모든 키가 존재하는지 확인."""
        result = calculate_year_end_settlement(
            employee="EMPX", tax_year=2025,
            total_salary=30_000_000, monthly_paid_income_tax=0,
        )
        expected_keys = {
            "contract_type", "tax_year", "employee", "total_salary",
            "earned_income_deduction", "earned_income",
            "personal_deduction", "special_income_deduction",
            "tax_base", "calculated_tax", "tax_credits",
            "determined_tax", "monthly_paid_tax",
            "refund_or_pay", "local_tax_settlement",
        }
        self.assertEqual(set(result.keys()), expected_keys)


class TestChildTaxCreditEdges(unittest.TestCase):
    """자녀세액공제 경계 테스트."""

    def _child_credit(self, n: int) -> float:
        return _mod._calc_child_tax_credit(n)

    def test_zero_children(self):
        self.assertAlmostEqual(self._child_credit(0), 0, delta=0.01)

    def test_one_child(self):
        self.assertAlmostEqual(self._child_credit(1), 150_000, delta=0.01)

    def test_two_children(self):
        self.assertAlmostEqual(self._child_credit(2), 350_000, delta=0.01)

    def test_three_children(self):
        self.assertAlmostEqual(self._child_credit(3), 650_000, delta=0.01)

    def test_four_children(self):
        self.assertAlmostEqual(self._child_credit(4), 950_000, delta=0.01)


if __name__ == "__main__":
    unittest.main()
