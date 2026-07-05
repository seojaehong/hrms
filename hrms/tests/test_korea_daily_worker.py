"""
일용근로자 급여 계산 테스트 — framework-free (plain unittest).

실행 방법:
    # 프로젝트 루트에서:
    python -m pytest hrms/tests/test_korea_daily_worker.py -v
    python -m unittest hrms.tests.test_korea_daily_worker -v
    python hrms/tests/test_korea_daily_worker.py -v

법적 근거 (2026년 기준):
  - 소득세법 제22조·제47조의2: 일용근로소득공제 150,000원
  - 소액부징수: 일급 187,000원 이하 소득세 0원
  - 분리과세: (일급 − 150,000) × 6% × (1 − 55%) = × 2.7%
  - 지방소득세: 소득세 × 10%
  - 10원 절사 적용
"""

from __future__ import annotations

import pathlib
import sys
import types
import unittest

# ---------------------------------------------------------------------------
# hrms/__init__.py 가 `import frappe`를 실행하므로 Frappe 없는 환경에서
# 테스트가 깨지는 것을 방지하기 위해 더미 모듈을 주입한다.
# daily_worker.py 자체는 frappe를 사용하지 않으므로 기능에 영향 없다.
# 직접 실행 시 sys.path에 스크립트 디렉터리만 등록되므로 repo 루트도 추가한다.
# ---------------------------------------------------------------------------
if "frappe" not in sys.modules:
    sys.modules["frappe"] = types.ModuleType("frappe")

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from hrms.regional.south_korea.daily_worker import (  # noqa: E402
    DAILY_TAX_EXEMPT_LIMIT,
    DAILY_WORKING_DEDUCTION_AMOUNT,
    calculate_daily_worker_payroll,
)


class TestDailyWorkerConstants(unittest.TestCase):
    """상수 값 검증."""

    def test_tax_exempt_limit(self):
        self.assertEqual(DAILY_TAX_EXEMPT_LIMIT, 187_000)

    def test_working_deduction_amount(self):
        self.assertEqual(DAILY_WORKING_DEDUCTION_AMOUNT, 150_000)


class TestCase1_FullyExempt(unittest.TestCase):
    """
    케이스 1: 일급 150,000 × 10일
    - 일급 ≤ 187,000 → 소액부징수 → 소득세 0
    - 비과세 임금 = 150,000 × 10 = 1,500,000
    - 과세 임금 = 0
    - 실수령액 = 1,500,000
    """

    def setUp(self):
        self.result = calculate_daily_worker_payroll(
            daily_wage=150_000,
            days_worked=10,
        )

    def test_contract_type(self):
        self.assertEqual(self.result["contract_type"], "korea_daily_worker_payroll_v1")

    def test_daily_wage(self):
        self.assertEqual(self.result["daily_wage"], 150_000.0)

    def test_days_worked(self):
        self.assertEqual(self.result["days_worked"], 10)

    def test_total_gross(self):
        self.assertEqual(self.result["total_gross"], 1_500_000.0)

    def test_tax_exempt_wages(self):
        # min(150_000, 187_000) × 10 = 1_500_000
        self.assertEqual(self.result["tax_exempt_wages"], 1_500_000.0)

    def test_taxable_wages(self):
        # 일급이 187,000 미만 → 과세 임금 없음
        self.assertEqual(self.result["taxable_wages"], 0.0)

    def test_daily_deduction(self):
        self.assertEqual(self.result["daily_deduction"], 1_500_000.0)

    def test_income_tax_per_day_is_zero(self):
        self.assertEqual(self.result["income_tax_per_day"], 0.0)

    def test_income_tax_total_is_zero(self):
        self.assertEqual(self.result["income_tax_total"], 0.0)

    def test_local_income_tax_total_is_zero(self):
        self.assertEqual(self.result["local_income_tax_total"], 0.0)

    def test_net_pay_equals_gross(self):
        self.assertEqual(self.result["net_pay"], 1_500_000.0)

    def test_employment_insurance_always_applies(self):
        self.assertTrue(self.result["applies_employment_insurance"])

    def test_industrial_accident_always_applies(self):
        self.assertTrue(self.result["applies_industrial_accident"])

    def test_pension_not_applied_by_default(self):
        # employment_period_months=0 (기본값)
        self.assertFalse(self.result["applies_pension"])

    def test_health_insurance_not_applied_by_default(self):
        self.assertFalse(self.result["applies_health_insurance"])


class TestCase2_PartiallyTaxable(unittest.TestCase):
    """
    케이스 2: 일급 200,000 × 5일
    - 소득세 과표: (200,000 − 150,000) × 2.7% = 1,350원/일 (10원 절사 후 1,350원)
    - 소득세 합계: 1,350 × 5 = 6,750원
    - 지방소득세: 6,750 × 10% = 675원 (10원 절사 = 670원)
      ※ 675원의 10원 절사 → 670원
    - tax_exempt_wages: 187,000 × 5 = 935,000
    - taxable_wages: 13,000 × 5 = 65,000
    - net_pay: 1,000,000 − 6,750 − 670 = 992,580
    """

    def setUp(self):
        self.result = calculate_daily_worker_payroll(
            daily_wage=200_000,
            days_worked=5,
        )

    def test_total_gross(self):
        self.assertEqual(self.result["total_gross"], 1_000_000.0)

    def test_tax_exempt_wages(self):
        # min(200_000, 187_000) × 5 = 935_000
        self.assertEqual(self.result["tax_exempt_wages"], 935_000.0)

    def test_taxable_wages(self):
        # (200_000 − 187_000) × 5 = 65_000
        self.assertEqual(self.result["taxable_wages"], 65_000.0)

    def test_income_tax_per_day(self):
        # (200,000 − 150,000) × 0.027 = 1,350 → 10원 절사 = 1,350
        self.assertEqual(self.result["income_tax_per_day"], 1_350.0)

    def test_income_tax_total(self):
        self.assertEqual(self.result["income_tax_total"], 6_750.0)

    def test_local_income_tax_total(self):
        # 6,750 × 0.10 = 675 → 10원 절사 = 670
        self.assertEqual(self.result["local_income_tax_total"], 670.0)

    def test_net_pay(self):
        # 1,000,000 − 6,750 − 670 = 992,580
        self.assertEqual(self.result["net_pay"], 992_580.0)

    def test_daily_deduction(self):
        self.assertEqual(self.result["daily_deduction"], 750_000.0)

    def test_employment_insurance_applies(self):
        self.assertTrue(self.result["applies_employment_insurance"])

    def test_industrial_accident_applies(self):
        self.assertTrue(self.result["applies_industrial_accident"])


class TestCase3_OneMonth_AllInsuranceApplied(unittest.TestCase):
    """
    케이스 3: 일급 250,000 × 30일 (employment_period_months=1 → 4대보험 전체 적용)
    - 소득세 과표: (250,000 − 150,000) × 2.7% = 2,700원/일 (10원 절사 = 2,700원)
    - 소득세 합계: 2,700 × 30 = 81,000원
    - 지방소득세: 81,000 × 10% = 8,100원 (10원 절사 = 8,100원)
    - tax_exempt_wages: 187,000 × 30 = 5,610,000
    - taxable_wages: 63,000 × 30 = 1,890,000
    - total_gross: 7,500,000
    - net_pay: 7,500,000 − 81,000 − 8,100 = 7,410,900
    """

    def setUp(self):
        self.result = calculate_daily_worker_payroll(
            daily_wage=250_000,
            days_worked=30,
            employment_period_months=1,
        )

    def test_total_gross(self):
        self.assertEqual(self.result["total_gross"], 7_500_000.0)

    def test_tax_exempt_wages(self):
        # min(250_000, 187_000) × 30 = 5_610_000
        self.assertEqual(self.result["tax_exempt_wages"], 5_610_000.0)

    def test_taxable_wages(self):
        # (250_000 − 187_000) × 30 = 1_890_000
        self.assertEqual(self.result["taxable_wages"], 1_890_000.0)

    def test_income_tax_per_day(self):
        # (250,000 − 150,000) × 0.027 = 2,700 → 10원 절사 = 2,700
        self.assertEqual(self.result["income_tax_per_day"], 2_700.0)

    def test_income_tax_total(self):
        self.assertEqual(self.result["income_tax_total"], 81_000.0)

    def test_local_income_tax_total(self):
        # 81,000 × 0.10 = 8,100 → 10원 절사 = 8,100
        self.assertEqual(self.result["local_income_tax_total"], 8_100.0)

    def test_net_pay(self):
        # 7,500,000 − 81,000 − 8,100 = 7,410,900
        self.assertEqual(self.result["net_pay"], 7_410_900.0)

    def test_pension_applies(self):
        # 1개월 이상 → 국민연금 적용
        self.assertTrue(self.result["applies_pension"])

    def test_health_insurance_applies(self):
        # 1개월 이상 → 건강보험 적용
        self.assertTrue(self.result["applies_health_insurance"])

    def test_employment_insurance_applies(self):
        self.assertTrue(self.result["applies_employment_insurance"])

    def test_industrial_accident_applies(self):
        self.assertTrue(self.result["applies_industrial_accident"])

    def test_daily_deduction(self):
        self.assertEqual(self.result["daily_deduction"], 4_500_000.0)


class TestCase4_ShortTerm_LimitedInsurance(unittest.TestCase):
    """
    케이스 4: 일급 250,000 × 25일 (employment_period_months=0, 1개월 미만)
    - 세금 계산은 케이스 3과 동일 (일수만 다름)
    - 국민연금 / 건강보험 미적용
    - 고용보험 / 산재보험 적용
    - 소득세: 2,700 × 25 = 67,500원
    - 지방소득세: 67,500 × 10% = 6,750 → 10원 절사 = 6,750
    - total_gross: 6,250,000
    - net_pay: 6,250,000 − 67,500 − 6,750 = 6,175,750
    """

    def setUp(self):
        self.result = calculate_daily_worker_payroll(
            daily_wage=250_000,
            days_worked=25,
            employment_period_months=0,
        )

    def test_total_gross(self):
        self.assertEqual(self.result["total_gross"], 6_250_000.0)

    def test_income_tax_per_day(self):
        self.assertEqual(self.result["income_tax_per_day"], 2_700.0)

    def test_income_tax_total(self):
        self.assertEqual(self.result["income_tax_total"], 67_500.0)

    def test_local_income_tax_total(self):
        # 67,500 × 0.10 = 6,750 → 10원 절사 = 6,750
        self.assertEqual(self.result["local_income_tax_total"], 6_750.0)

    def test_net_pay(self):
        # 6,250,000 − 67,500 − 6,750 = 6,175,750
        self.assertEqual(self.result["net_pay"], 6_175_750.0)

    def test_pension_not_applies(self):
        # 1개월 미만 → 국민연금 미적용
        self.assertFalse(self.result["applies_pension"])

    def test_health_insurance_not_applies(self):
        # 1개월 미만 → 건강보험 미적용
        self.assertFalse(self.result["applies_health_insurance"])

    def test_employment_insurance_applies(self):
        # 단기 일용직도 고용보험 적용
        self.assertTrue(self.result["applies_employment_insurance"])

    def test_industrial_accident_applies(self):
        # 산재보험은 항상 적용
        self.assertTrue(self.result["applies_industrial_accident"])


class TestAdditionalWages(unittest.TestCase):
    """additional_wages 처리 검증."""

    def test_additional_wages_add_to_gross_and_net(self):
        """식대 등 추가 비과세 수당은 total_gross 및 net_pay에 포함된다."""
        base = calculate_daily_worker_payroll(daily_wage=200_000, days_worked=5)
        with_meal = calculate_daily_worker_payroll(
            daily_wage=200_000, days_worked=5, additional_wages=100_000
        )
        self.assertEqual(with_meal["total_gross"], base["total_gross"] + 100_000)
        self.assertEqual(with_meal["net_pay"], base["net_pay"] + 100_000)

    def test_additional_wages_do_not_affect_income_tax(self):
        """추가 비과세 수당은 소득세 과표에 영향을 주지 않는다."""
        base = calculate_daily_worker_payroll(daily_wage=200_000, days_worked=5)
        with_meal = calculate_daily_worker_payroll(
            daily_wage=200_000, days_worked=5, additional_wages=100_000
        )
        self.assertEqual(with_meal["income_tax_per_day"], base["income_tax_per_day"])
        self.assertEqual(with_meal["income_tax_total"], base["income_tax_total"])
        self.assertEqual(with_meal["local_income_tax_total"], base["local_income_tax_total"])

    def test_additional_wages_do_not_affect_exempt_taxable_split(self):
        """추가 비과세 수당은 tax_exempt_wages / taxable_wages 계산에 영향 없다."""
        base = calculate_daily_worker_payroll(daily_wage=200_000, days_worked=5)
        with_meal = calculate_daily_worker_payroll(
            daily_wage=200_000, days_worked=5, additional_wages=50_000
        )
        self.assertEqual(with_meal["tax_exempt_wages"], base["tax_exempt_wages"])
        self.assertEqual(with_meal["taxable_wages"], base["taxable_wages"])


class TestEdgeCases(unittest.TestCase):
    """경계값 및 에러 처리 테스트."""

    def test_exactly_at_exempt_limit(self):
        """일급 = 187,000원 → 소액부징수, 소득세 0."""
        result = calculate_daily_worker_payroll(daily_wage=187_000, days_worked=1)
        self.assertEqual(result["income_tax_per_day"], 0.0)
        self.assertEqual(result["income_tax_total"], 0.0)

    def test_just_above_exempt_limit(self):
        """일급 = 187,001원 → 과세 발생."""
        result = calculate_daily_worker_payroll(daily_wage=187_001, days_worked=1)
        # (187,001 − 150,000) × 0.027 = 999.027 → 10원 절사 = 990
        self.assertEqual(result["income_tax_per_day"], 990.0)

    def test_zero_days_worked(self):
        """근무일수 0일."""
        result = calculate_daily_worker_payroll(daily_wage=250_000, days_worked=0)
        self.assertEqual(result["total_gross"], 0.0)
        self.assertEqual(result["income_tax_total"], 0.0)
        self.assertEqual(result["net_pay"], 0.0)

    def test_contract_type_field(self):
        """contract_type 고정값 확인."""
        result = calculate_daily_worker_payroll(daily_wage=100_000, days_worked=1)
        self.assertEqual(result["contract_type"], "korea_daily_worker_payroll_v1")

    def test_negative_daily_wage_raises(self):
        """음수 일급은 ValueError 발생."""
        with self.assertRaises(ValueError):
            calculate_daily_worker_payroll(daily_wage=-1, days_worked=1)

    def test_negative_days_worked_raises(self):
        """음수 근무일수는 ValueError 발생."""
        with self.assertRaises(ValueError):
            calculate_daily_worker_payroll(daily_wage=150_000, days_worked=-1)

    def test_employment_period_months_exactly_one(self):
        """연속 근무 1개월: 국민연금/건강보험 적용."""
        result = calculate_daily_worker_payroll(
            daily_wage=200_000, days_worked=1, employment_period_months=1
        )
        self.assertTrue(result["applies_pension"])
        self.assertTrue(result["applies_health_insurance"])

    def test_employment_period_months_zero(self):
        """연속 근무 0개월: 국민연금/건강보험 미적용."""
        result = calculate_daily_worker_payroll(
            daily_wage=200_000, days_worked=1, employment_period_months=0
        )
        self.assertFalse(result["applies_pension"])
        self.assertFalse(result["applies_health_insurance"])

    def test_ten_won_floor_applied(self):
        """10원 절사 적용 확인: 187,001원일 때 1원 단위 제거."""
        result = calculate_daily_worker_payroll(daily_wage=187_001, days_worked=1)
        # 소득세는 10의 배수여야 함
        self.assertEqual(result["income_tax_per_day"] % 10, 0.0)

    def test_float_input_coercion(self):
        """float 입력 정상 처리."""
        result = calculate_daily_worker_payroll(
            daily_wage=200_000.0, days_worked=5, additional_wages=0.0
        )
        self.assertIsInstance(result["total_gross"], float)


if __name__ == "__main__":
    unittest.main()
