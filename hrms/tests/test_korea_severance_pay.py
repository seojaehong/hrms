"""근퇴법 8조 퇴직금 계산기 테스트.

framework-free: frappe import 없음.
모든 테스트는 unittest.TestCase 직접 상속.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import pathlib
import sys
import types
import unittest

# ---------------------------------------------------------------------------
# 모듈 동적 로드 (frappe 미설치 환경 대응)
# ---------------------------------------------------------------------------

ROOT = pathlib.Path(__file__).resolve().parents[2]
_MOD_PATH = ROOT / "hrms" / "regional" / "south_korea" / "severance_pay.py"

spec = importlib.util.spec_from_file_location("severance_pay", _MOD_PATH)
_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_mod)

calculate_continuous_service_days = _mod.calculate_continuous_service_days
calculate_average_wage = _mod.calculate_average_wage
calculate_severance_pay = _mod.calculate_severance_pay
estimate_irp_contribution = _mod.estimate_irp_contribution
IRP_MANDATORY_THRESHOLD = _mod.IRP_MANDATORY_THRESHOLD


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def _d(s: str) -> dt.date:
    return dt.date.fromisoformat(s)


def _wage_record(date: str, amount: float, wage_type: str = "base") -> dict:
    return {"date": _d(date), "amount": amount, "wage_type": wage_type}


# ---------------------------------------------------------------------------
# calculate_continuous_service_days
# ---------------------------------------------------------------------------

class TestContinuousServiceDays(unittest.TestCase):

    def test_basic_calculation(self):
        """입사 2023-01-01 ~ 퇴직 2024-01-01 → 366일 (2023년 윤년 아님: 365일)."""
        result = calculate_continuous_service_days(_d("2023-01-01"), _d("2024-01-01"))
        self.assertEqual(result, 365)

    def test_exactly_one_year_leap(self):
        """입사 2024-01-01 ~ 퇴직 2025-01-01 → 366일 (2024년 윤년)."""
        result = calculate_continuous_service_days(_d("2024-01-01"), _d("2025-01-01"))
        self.assertEqual(result, 366)

    def test_300_days_less_than_one_year(self):
        result = calculate_continuous_service_days(_d("2023-01-01"), _d("2023-10-28"))
        self.assertEqual(result, 300)

    def test_same_date_returns_zero(self):
        result = calculate_continuous_service_days(_d("2023-01-01"), _d("2023-01-01"))
        self.assertEqual(result, 0)

    def test_severance_before_hire_returns_zero(self):
        result = calculate_continuous_service_days(_d("2023-06-01"), _d("2023-01-01"))
        self.assertEqual(result, 0)

    def test_exclusion_inside_range(self):
        """2년 재직 중 무단결근 10일 → 재직일수 730-10=720."""
        hire = _d("2021-01-01")
        sev = _d("2023-01-01")  # 730일
        excl = [(_d("2022-06-01"), _d("2022-06-10"))]  # 10일
        result = calculate_continuous_service_days(hire, sev, excl)
        self.assertEqual(result, 720)

    def test_exclusion_fully_outside_range_no_effect(self):
        """exclusion이 재직 기간 밖이면 영향 없음."""
        hire = _d("2022-01-01")
        sev = _d("2023-01-01")  # 365일
        excl = [(_d("2020-01-01"), _d("2020-12-31"))]
        result = calculate_continuous_service_days(hire, sev, excl)
        self.assertEqual(result, 365)

    def test_exclusion_overlapping_hire_date(self):
        """exclusion 시작이 hire_date 이전이어도 교집합만 차감."""
        hire = _d("2022-01-01")
        sev = _d("2023-01-01")  # 365일
        # hire_date ~ 2022-01-10: 10일 차감 (2022-01-01~2022-01-10 = 10일)
        excl = [(_d("2021-12-01"), _d("2022-01-10"))]
        result = calculate_continuous_service_days(hire, sev, excl)
        self.assertEqual(result, 355)

    def test_exclusion_overlapping_severance_date(self):
        """exclusion 종료가 severance_date 이후이어도 교집합만 차감."""
        hire = _d("2022-01-01")
        sev = _d("2023-01-01")  # 365일
        # 2022-12-25 ~ 2022-12-31 = 7일 차감
        excl = [(_d("2022-12-25"), _d("2023-02-01"))]
        result = calculate_continuous_service_days(hire, sev, excl)
        self.assertEqual(result, 358)

    def test_multiple_exclusions(self):
        hire = _d("2022-01-01")
        sev = _d("2023-01-01")  # 365일
        excl = [
            (_d("2022-03-01"), _d("2022-03-05")),   # 5일
            (_d("2022-09-01"), _d("2022-09-15")),   # 15일
        ]
        result = calculate_continuous_service_days(hire, sev, excl)
        self.assertEqual(result, 345)


# ---------------------------------------------------------------------------
# calculate_average_wage
# ---------------------------------------------------------------------------

class TestAverageWage(unittest.TestCase):

    def test_simple_monthly_base_wages(self):
        """단순 기본급 3개월: 각 3,000,000원."""
        sev = _d("2023-10-01")
        # 산정기간: 2023-07-01 ~ 2023-09-30 = 92일
        records = [
            _wage_record("2023-07-25", 3_000_000),
            _wage_record("2023-08-25", 3_000_000),
            _wage_record("2023-09-25", 3_000_000),
        ]
        result = calculate_average_wage(severance_date=sev, wage_records=records)

        self.assertEqual(result["calculation_period_start"], "2023-07-01")
        self.assertEqual(result["calculation_period_end"], "2023-09-30")
        self.assertEqual(result["total_days"], 92)
        self.assertAlmostEqual(result["total_wage_amount"], 9_000_000)
        expected_daily = 9_000_000 / 92
        self.assertAlmostEqual(result["average_wage_per_day"], expected_daily, places=4)

    def test_bonus_apportioned_3_over_12(self):
        """연간 상여금 12,000,000원 → 3/12 = 3,000,000원 산입."""
        sev = _d("2023-10-01")
        records = [
            _wage_record("2023-07-25", 3_000_000, "base"),
            _wage_record("2023-01-01", 12_000_000, "bonus"),  # 연간 상여, 날짜는 연초
        ]
        result = calculate_average_wage(severance_date=sev, wage_records=records)
        # bonus 3/12 = 3,000,000 + base 3,000,000 = 6,000,000
        self.assertAlmostEqual(result["total_wage_amount"], 6_000_000)

    def test_annual_leave_apportioned(self):
        """연차수당 연간 2,400,000원 → 3/12 = 600,000원 산입."""
        sev = _d("2023-10-01")
        records = [
            _wage_record("2023-01-01", 2_400_000, "annual_leave"),
        ]
        result = calculate_average_wage(severance_date=sev, wage_records=records)
        self.assertAlmostEqual(result["total_wage_amount"], 600_000)

    def test_period_days_override(self):
        """period_days=90 명시 → 총일수 90으로 계산."""
        sev = _d("2023-10-01")
        records = [_wage_record("2023-09-25", 3_000_000)]
        result = calculate_average_wage(
            severance_date=sev, wage_records=records, period_days=90
        )
        self.assertEqual(result["total_days"], 90)

    def test_short_service_uses_hire_date_as_floor(self):
        """재직 기간 < 3개월: hire_date를 하한으로 사용."""
        hire = _d("2023-08-15")
        sev = _d("2023-10-01")  # 47일 재직
        records = [_wage_record("2023-09-25", 1_500_000)]
        result = calculate_average_wage(
            severance_date=sev, wage_records=records, hire_date=hire
        )
        # period_start = hire_date (2023-08-15), period_end = 2023-09-30
        self.assertEqual(result["calculation_period_start"], "2023-08-15")
        self.assertEqual(result["calculation_period_end"], "2023-09-30")
        expected_days = (dt.date(2023, 9, 30) - dt.date(2023, 8, 15)).days + 1
        self.assertEqual(result["total_days"], expected_days)

    def test_severance_date_first_of_month(self):
        """퇴직일 = 1일: 산정 기간이 전월 말일로 끝나야 함 (§6-3)."""
        sev = _d("2023-07-01")  # 퇴직일 = 7월 1일
        # period_end = 2023-06-30, period_start = 2023-04-01
        records = [
            _wage_record("2023-04-25", 3_000_000),
            _wage_record("2023-05-25", 3_000_000),
            _wage_record("2023-06-25", 3_000_000),
        ]
        result = calculate_average_wage(severance_date=sev, wage_records=records)
        self.assertEqual(result["calculation_period_start"], "2023-04-01")
        self.assertEqual(result["calculation_period_end"], "2023-06-30")
        # 4월 30일 + 5월 31일 + 6월 30일 = 91일
        self.assertEqual(result["total_days"], 91)

    def test_exclusion_filters_wage_records(self):
        """exclusion 기간 내 wage_record 는 집계 제외."""
        sev = _d("2023-10-01")
        records = [
            _wage_record("2023-07-25", 3_000_000),
            _wage_record("2023-08-25", 3_000_000),  # exclusion 기간 내
            _wage_record("2023-09-25", 3_000_000),
        ]
        excl = [(_d("2023-08-01"), _d("2023-08-31"))]
        result = calculate_average_wage(
            severance_date=sev, wage_records=records, exclusions=excl
        )
        # 8월 레코드 제외 → 총액 6,000,000
        self.assertAlmostEqual(result["total_wage_amount"], 6_000_000)

    def test_exclusion_symmetric_total_days_reduced(self):
        """exclusion 기간이 total_days(분모)에서도 대칭 차감되어야 함.

        8월(31일) 무급휴직 → 분자도 제외, 분모도 92-31=61일.
        결과: 6,000,000/61 ≈ 98,360.66  (92로 나누면 65,217로 낮아져 잘못됨).
        """
        sev = _d("2023-10-01")  # 산정기간: 07-01 ~ 09-30 = 92일
        records = [
            _wage_record("2023-07-25", 3_000_000),
            # 8월 임금 없음 (무급휴직)
            _wage_record("2023-09-25", 3_000_000),
        ]
        excl = [(_d("2023-08-01"), _d("2023-08-31"))]
        result = calculate_average_wage(
            severance_date=sev, wage_records=records, exclusions=excl
        )
        # 분모: 92 - 31 = 61
        self.assertEqual(result["total_days"], 61)
        # 분자: 6,000,000
        self.assertAlmostEqual(result["total_wage_amount"], 6_000_000)
        expected_daily = 6_000_000 / 61
        self.assertAlmostEqual(result["average_wage_per_day"], expected_daily, places=4)

    def test_out_of_period_base_record_excluded(self):
        """산정 기간 밖의 base 레코드는 산입 제외."""
        sev = _d("2023-10-01")  # 산정기간: 07-01 ~ 09-30
        records = [
            _wage_record("2023-09-25", 3_000_000),        # 기간 내
            _wage_record("2023-05-25", 1_000_000),        # 기간 밖 (5월)
        ]
        result = calculate_average_wage(severance_date=sev, wage_records=records)
        # 5월 레코드 제외 → 3,000,000만 산입
        self.assertAlmostEqual(result["total_wage_amount"], 3_000_000)

    def test_mixed_wage_types(self):
        """base + allowance + bonus 혼합."""
        sev = _d("2024-01-01")
        records = [
            _wage_record("2023-10-25", 2_000_000, "base"),
            _wage_record("2023-11-25", 2_000_000, "base"),
            _wage_record("2023-12-25", 2_000_000, "base"),
            _wage_record("2023-10-25", 500_000, "allowance"),
            _wage_record("2023-01-01", 6_000_000, "bonus"),   # 연간 → 3/12 = 1,500,000
        ]
        result = calculate_average_wage(severance_date=sev, wage_records=records)
        expected = 2_000_000 * 3 + 500_000 + 6_000_000 * 3 / 12
        self.assertAlmostEqual(result["total_wage_amount"], expected)

    def test_february_period_start_on_march_31(self):
        """퇴직일 3월 31일: 3개월 전 = 12월 31일."""
        sev = _d("2024-04-01")  # period_end = 2024-03-31
        result = calculate_average_wage(severance_date=sev, wage_records=[])
        self.assertEqual(result["calculation_period_start"], "2024-01-01")
        self.assertEqual(result["calculation_period_end"], "2024-03-31")


# ---------------------------------------------------------------------------
# calculate_severance_pay
# ---------------------------------------------------------------------------

class TestCalculateSeverancePay(unittest.TestCase):

    def test_less_than_one_year_qualified_false(self):
        """300일 재직 → 퇴직금 없음."""
        hire = _d("2023-01-01")
        sev = hire + dt.timedelta(days=300)
        result = calculate_severance_pay(
            hire_date=hire,
            severance_date=sev,
            average_wage_per_day=100_000,
        )
        self.assertFalse(result["qualified_for_severance"])
        self.assertEqual(result["severance_pay_amount"], 0.0)
        self.assertEqual(result["continuous_service_days"], 300)

    def test_exactly_one_year(self):
        """정확히 365일 재직 → 퇴직금 = avg × 30 × (365/365) = avg × 30."""
        hire = _d("2023-01-01")
        sev = _d("2024-01-01")  # 365일
        avg_daily = 100_000.0
        result = calculate_severance_pay(
            hire_date=hire,
            severance_date=sev,
            average_wage_per_day=avg_daily,
        )
        self.assertTrue(result["qualified_for_severance"])
        # 100,000 × 30 × (365/365) = 3,000,000
        self.assertEqual(result["continuous_service_days"], 365)
        expected = int(avg_daily * 30 * 365 / 365)
        self.assertEqual(result["severance_pay_amount"], float(expected))

    def test_five_years(self):
        """5년(1826일) 재직 → 퇴직금 = avg × 30 × (1826/365)."""
        hire = _d("2019-01-01")
        sev = _d("2024-01-01")  # 1826일 (2020 윤년 포함)
        avg_daily = 80_000.0
        result = calculate_severance_pay(
            hire_date=hire,
            severance_date=sev,
            average_wage_per_day=avg_daily,
        )
        self.assertTrue(result["qualified_for_severance"])
        svc_days = (sev - hire).days
        self.assertEqual(result["continuous_service_days"], svc_days)
        expected = int(avg_daily * 30 * svc_days / 365)
        self.assertEqual(result["severance_pay_amount"], float(expected))

    def test_ordinary_wage_higher_than_average(self):
        """통상임금 > 평균임금 → ordinary 사용."""
        hire = _d("2022-01-01")
        sev = _d("2023-01-01")  # 365일
        result = calculate_severance_pay(
            hire_date=hire,
            severance_date=sev,
            average_wage_per_day=50_000.0,
            ordinary_wage_per_day=80_000.0,
        )
        self.assertEqual(result["wage_used_reason"], "ordinary")
        self.assertEqual(result["wage_used_per_day"], 80_000.0)
        expected = int(80_000.0 * 30 * 365 / 365)
        self.assertEqual(result["severance_pay_amount"], float(expected))

    def test_average_wage_higher_than_ordinary(self):
        """평균임금 > 통상임금 → average 사용."""
        hire = _d("2022-01-01")
        sev = _d("2023-01-01")
        result = calculate_severance_pay(
            hire_date=hire,
            severance_date=sev,
            average_wage_per_day=100_000.0,
            ordinary_wage_per_day=80_000.0,
        )
        self.assertEqual(result["wage_used_reason"], "average")
        self.assertEqual(result["wage_used_per_day"], 100_000.0)

    def test_ordinary_wage_none_uses_average(self):
        """ordinary_wage_per_day=None → average 사용."""
        hire = _d("2022-01-01")
        sev = _d("2023-01-01")
        result = calculate_severance_pay(
            hire_date=hire,
            severance_date=sev,
            average_wage_per_day=100_000.0,
            ordinary_wage_per_day=None,
        )
        self.assertEqual(result["wage_used_reason"], "average")

    def test_with_exclusion_reduces_service_days(self):
        """exclusion 30일 → 재직일수 감소."""
        hire = _d("2022-01-01")
        sev = _d("2023-01-01")  # 365일
        excl = [(_d("2022-06-01"), _d("2022-06-30"))]  # 30일
        result = calculate_severance_pay(
            hire_date=hire,
            severance_date=sev,
            average_wage_per_day=100_000.0,
            exclusions=excl,
        )
        self.assertEqual(result["continuous_service_days"], 335)
        # 335 < 365 → 미발생
        self.assertFalse(result["qualified_for_severance"])

    def test_truncation_applied(self):
        """원단위 절사 확인: avg × 30 × (days/365) 소수점 버림."""
        hire = _d("2022-01-01")
        sev = _d("2023-01-01")  # 365일
        avg_daily = 33_333.33  # 소수점 있음
        result = calculate_severance_pay(
            hire_date=hire,
            severance_date=sev,
            average_wage_per_day=avg_daily,
        )
        raw = avg_daily * 30 * 365 / 365
        expected = float(int(raw))
        self.assertEqual(result["severance_pay_amount"], expected)

    def test_calculation_formula_contains_key_parts(self):
        """formula 문자열에 핵심 요소 포함 확인."""
        hire = _d("2022-01-01")
        sev = _d("2023-01-01")
        result = calculate_severance_pay(
            hire_date=hire,
            severance_date=sev,
            average_wage_per_day=100_000.0,
        )
        formula = result["calculation_formula"]
        self.assertIn("30", formula)
        self.assertIn("365", formula)
        self.assertIn("average", formula)

    def test_not_qualified_formula_mentions_reason(self):
        """미발생 시 formula에 365일 미충족 사유 언급."""
        hire = _d("2023-01-01")
        sev = hire + dt.timedelta(days=200)
        result = calculate_severance_pay(
            hire_date=hire,
            severance_date=sev,
            average_wage_per_day=100_000.0,
        )
        self.assertIn("365", result["calculation_formula"])

    def test_severance_date_on_first_of_month(self):
        """퇴직일 = 1일 → (spec §6-3) 재직일수 계산 이상 없어야 함."""
        hire = _d("2022-04-01")
        sev = _d("2023-04-01")  # 365일
        result = calculate_severance_pay(
            hire_date=hire,
            severance_date=sev,
            average_wage_per_day=100_000.0,
        )
        self.assertEqual(result["continuous_service_days"], 365)
        self.assertTrue(result["qualified_for_severance"])

    def test_exclusion_outside_range_no_effect_on_qualification(self):
        """재직 기간 밖의 exclusion은 서비스데이에 영향 없음."""
        hire = _d("2022-01-01")
        sev = _d("2023-01-01")
        excl = [(_d("2020-01-01"), _d("2021-01-01"))]
        result = calculate_severance_pay(
            hire_date=hire,
            severance_date=sev,
            average_wage_per_day=100_000.0,
            exclusions=excl,
        )
        self.assertEqual(result["continuous_service_days"], 365)
        self.assertTrue(result["qualified_for_severance"])


# ---------------------------------------------------------------------------
# estimate_irp_contribution
# ---------------------------------------------------------------------------

class TestEstimateIrpContribution(unittest.TestCase):

    def test_above_threshold_requires_irp(self):
        """3,000,000원 이상 → IRP 의무이체."""
        result = estimate_irp_contribution(5_000_000)
        self.assertTrue(result["requires_irp_transfer"])
        self.assertEqual(result["irp_transfer_amount"], 5_000_000)
        self.assertEqual(result["cash_payout_amount"], 0.0)

    def test_exactly_at_threshold_requires_irp(self):
        result = estimate_irp_contribution(3_000_000)
        self.assertTrue(result["requires_irp_transfer"])

    def test_below_threshold_cash_payout(self):
        result = estimate_irp_contribution(2_999_999)
        self.assertFalse(result["requires_irp_transfer"])
        self.assertEqual(result["cash_payout_amount"], 2_999_999)

    def test_zero_amount(self):
        result = estimate_irp_contribution(0.0)
        self.assertFalse(result["requires_irp_transfer"])

    def test_irp_not_required_flag(self):
        """irp_account_required=False → threshold 이상이어도 현금 지급."""
        result = estimate_irp_contribution(10_000_000, irp_account_required=False)
        self.assertFalse(result["requires_irp_transfer"])
        self.assertEqual(result["cash_payout_amount"], 10_000_000)

    def test_threshold_constant(self):
        """법정 기준값 300만원 확인."""
        self.assertEqual(IRP_MANDATORY_THRESHOLD, 3_000_000)

    def test_result_includes_note(self):
        result = estimate_irp_contribution(5_000_000)
        self.assertIn("note", result)
        self.assertIn("IRP", result["note"])


# ---------------------------------------------------------------------------
# 통합 시나리오: calculate_average_wage + calculate_severance_pay
# ---------------------------------------------------------------------------

class TestIntegrationScenarios(unittest.TestCase):

    def test_full_flow_5_years_with_bonus(self):
        """5년 재직, 기본급 + 상여금 통합 흐름."""
        hire = _d("2019-01-01")
        sev = _d("2024-01-01")

        records = [
            _wage_record("2023-10-25", 3_000_000, "base"),
            _wage_record("2023-11-25", 3_000_000, "base"),
            _wage_record("2023-12-25", 3_000_000, "base"),
            _wage_record("2023-01-01", 12_000_000, "bonus"),  # 연간 → 3/12 = 3,000,000
        ]

        avg_result = calculate_average_wage(
            severance_date=sev,
            wage_records=records,
            hire_date=hire,
        )

        sev_result = calculate_severance_pay(
            hire_date=hire,
            severance_date=sev,
            average_wage_per_day=avg_result["average_wage_per_day"],
        )

        self.assertTrue(sev_result["qualified_for_severance"])
        # 총임금 = 9,000,000 + 3,000,000 = 12,000,000
        self.assertAlmostEqual(avg_result["total_wage_amount"], 12_000_000)
        # 재직일수 = 2019-01-01 ~ 2024-01-01 = 1826일 (2020 윤년)
        self.assertEqual(sev_result["continuous_service_days"], 1826)
        # IRP 검증
        irp = estimate_irp_contribution(sev_result["severance_pay_amount"])
        self.assertTrue(irp["requires_irp_transfer"])

    def test_full_flow_ordinary_wage_fallback(self):
        """통상임금 > 평균임금 fallback 통합."""
        hire = _d("2022-01-01")
        sev = _d("2023-01-01")
        records = [
            _wage_record("2022-10-25", 1_500_000, "base"),
            _wage_record("2022-11-25", 1_500_000, "base"),
            _wage_record("2022-12-25", 1_500_000, "base"),
        ]
        avg_result = calculate_average_wage(
            severance_date=sev, wage_records=records
        )
        avg_daily = avg_result["average_wage_per_day"]

        # 통상임금을 평균임금보다 높게 설정
        ordinary_daily = avg_daily * 1.5

        sev_result = calculate_severance_pay(
            hire_date=hire,
            severance_date=sev,
            average_wage_per_day=avg_daily,
            ordinary_wage_per_day=ordinary_daily,
        )
        self.assertEqual(sev_result["wage_used_reason"], "ordinary")
        self.assertAlmostEqual(sev_result["wage_used_per_day"], ordinary_daily)

    def test_under_one_year_irp_not_applicable(self):
        """1년 미만 → 퇴직금 0 → IRP 불필요."""
        hire = _d("2023-01-01")
        sev = hire + dt.timedelta(days=300)
        sev_result = calculate_severance_pay(
            hire_date=hire,
            severance_date=sev,
            average_wage_per_day=100_000.0,
        )
        self.assertEqual(sev_result["severance_pay_amount"], 0.0)
        irp = estimate_irp_contribution(sev_result["severance_pay_amount"])
        self.assertFalse(irp["requires_irp_transfer"])


# ---------------------------------------------------------------------------
# 엣지 케이스 추가
# ---------------------------------------------------------------------------

class TestEdgeCases(unittest.TestCase):

    def test_bonus_only_records(self):
        """상여만 있는 경우 avg wage 는 3/12 산입분 / 총일수."""
        sev = _d("2023-10-01")
        records = [_wage_record("2023-01-01", 12_000_000, "bonus")]
        result = calculate_average_wage(severance_date=sev, wage_records=records)
        # 3/12 = 3,000,000
        self.assertAlmostEqual(result["total_wage_amount"], 3_000_000)
        expected_daily = 3_000_000 / result["total_days"]
        self.assertAlmostEqual(result["average_wage_per_day"], expected_daily, places=4)

    def test_service_less_than_3_months_wage_period(self):
        """재직 2개월: average wage 산정 기간이 hire_date 기준."""
        hire = _d("2023-08-01")
        sev = _d("2023-10-01")   # 61일 재직, 퇴직금 자격 없음
        records = [
            _wage_record("2023-08-25", 2_000_000),
            _wage_record("2023-09-25", 2_000_000),
        ]
        avg_result = calculate_average_wage(
            severance_date=sev, wage_records=records, hire_date=hire
        )
        self.assertEqual(avg_result["calculation_period_start"], "2023-08-01")
        sev_result = calculate_severance_pay(
            hire_date=hire,
            severance_date=sev,
            average_wage_per_day=avg_result["average_wage_per_day"],
        )
        self.assertFalse(sev_result["qualified_for_severance"])

    def test_unknown_wage_type_treated_as_base(self):
        """알 수 없는 wage_type은 base(전액 산입) 처리."""
        sev = _d("2023-10-01")
        records = [_wage_record("2023-09-25", 1_000_000, "custom_allowance")]
        result = calculate_average_wage(severance_date=sev, wage_records=records)
        # 전액 산입: 1,000,000
        self.assertAlmostEqual(result["total_wage_amount"], 1_000_000)

    def test_multiple_bonus_records_summed_then_apportioned(self):
        """상여 2건 → 합산 후 3/12 처리."""
        sev = _d("2023-10-01")
        records = [
            _wage_record("2023-06-01", 6_000_000, "bonus"),
            _wage_record("2023-12-01", 6_000_000, "bonus"),
        ]
        result = calculate_average_wage(severance_date=sev, wage_records=records)
        # 합산 12,000,000 × 3/12 = 3,000,000
        self.assertAlmostEqual(result["total_wage_amount"], 3_000_000)

    def test_severance_date_feb_29_leap_year(self):
        """퇴직일 = 윤년 3월 1일: 3개월 전 = 12월 1일."""
        sev = _d("2024-03-01")  # 윤년 2024
        result = calculate_average_wage(severance_date=sev, wage_records=[])
        # period_start = 2023-12-01, period_end = 2024-02-29
        self.assertEqual(result["calculation_period_start"], "2023-12-01")
        self.assertEqual(result["calculation_period_end"], "2024-02-29")
        # 12월 31일 + 1월 31일 + 2월 29일 = 91일
        self.assertEqual(result["total_days"], 91)

    def test_result_keys_completeness(self):
        """반환 딕셔너리 키 완전성 검증."""
        hire = _d("2022-01-01")
        sev = _d("2023-01-01")
        sev_result = calculate_severance_pay(
            hire_date=hire,
            severance_date=sev,
            average_wage_per_day=100_000.0,
            ordinary_wage_per_day=90_000.0,
        )
        required_keys = {
            "continuous_service_days",
            "qualified_for_severance",
            "average_wage_per_day",
            "ordinary_wage_per_day",
            "wage_used_per_day",
            "wage_used_reason",
            "severance_pay_amount",
            "calculation_formula",
        }
        self.assertEqual(required_keys, set(sev_result.keys()))

    def test_avg_wage_result_keys_completeness(self):
        avg_result = calculate_average_wage(
            severance_date=_d("2023-10-01"), wage_records=[]
        )
        required_keys = {
            "calculation_period_start",
            "calculation_period_end",
            "total_wage_amount",
            "total_days",
            "average_wage",
            "average_wage_per_day",
        }
        self.assertEqual(required_keys, set(avg_result.keys()))


# ---------------------------------------------------------------------------
# API 레이어 스모크 테스트 (severance_pay_api.py)
# FakeFrappe 심 없이 frappe를 임시 모듈로 대체
# ---------------------------------------------------------------------------

_API_MOD_PATH = ROOT / "hrms" / "regional" / "south_korea" / "severance_pay_api.py"


class FakeFrappeError(Exception):
    pass


class _FakeFrappeForApi(types.ModuleType):
    """severance_pay_api.py 가 필요한 frappe 심."""

    def whitelist(self, *args, **kwargs):
        return lambda fn: fn

    def throw(self, message, *args, **kwargs):
        raise FakeFrappeError(message)

    local = types.SimpleNamespace(form_dict={})


class TestSeverancePayApi(unittest.TestCase):

    def setUp(self):
        fake_frappe = _FakeFrappeForApi("frappe")
        sys.modules["frappe"] = fake_frappe
        spec_api = importlib.util.spec_from_file_location("severance_pay_api", _API_MOD_PATH)
        self._api = importlib.util.module_from_spec(spec_api)
        spec_api.loader.exec_module(self._api)

    def tearDown(self):
        sys.modules.pop("frappe", None)
        sys.modules.pop("severance_pay_api", None)

    def test_calculate_severance_preview_happy_path(self):
        payload = {
            "hire_date": "2022-01-01",
            "severance_date": "2023-01-01",
            "wage_records": [
                {"date": "2022-10-25", "amount": 3_000_000, "wage_type": "base"},
                {"date": "2022-11-25", "amount": 3_000_000, "wage_type": "base"},
                {"date": "2022-12-25", "amount": 3_000_000, "wage_type": "base"},
            ],
        }
        result = self._api.calculate_severance_preview(payload)
        self.assertIn("average_wage_result", result)
        self.assertIn("severance_result", result)
        self.assertTrue(result["severance_result"]["qualified_for_severance"])

    def test_calculate_severance_preview_with_exclusions_json_string(self):
        """exclusions가 JSON 문자열로 도착하는 웹 요청 패턴."""
        import json
        excl_json = json.dumps([{"from": "2022-06-01", "to": "2022-06-30"}])
        payload = {
            "hire_date": "2022-01-01",
            "severance_date": "2023-01-01",
            "wage_records": [
                {"date": "2022-10-25", "amount": 3_000_000, "wage_type": "base"},
            ],
            "exclusions": excl_json,
        }
        result = self._api.calculate_severance_preview(payload)
        # exclusion 30일 → 재직일수 335 → 미발생
        self.assertFalse(result["severance_result"]["qualified_for_severance"])

    def test_missing_required_fields_raises(self):
        payload = {"hire_date": "2022-01-01"}  # severance_date, wage_records 없음
        with self.assertRaises(FakeFrappeError):
            self._api.calculate_severance_preview(payload)

    def test_invalid_date_raises(self):
        payload = {
            "hire_date": "not-a-date",
            "severance_date": "2023-01-01",
            "wage_records": [],
        }
        with self.assertRaises(FakeFrappeError):
            self._api.calculate_severance_preview(payload)

    def test_severance_before_hire_raises(self):
        payload = {
            "hire_date": "2023-06-01",
            "severance_date": "2022-01-01",
            "wage_records": [],
        }
        with self.assertRaises(FakeFrappeError):
            self._api.calculate_severance_preview(payload)

    def test_estimate_irp_preview_above_threshold(self):
        payload = {"severance_pay_amount": 5_000_000}
        result = self._api.estimate_irp_preview(payload)
        self.assertTrue(result["requires_irp_transfer"])

    def test_estimate_irp_preview_below_threshold(self):
        payload = {"severance_pay_amount": 1_000_000}
        result = self._api.estimate_irp_preview(payload)
        self.assertFalse(result["requires_irp_transfer"])

    def test_ordinary_wage_zero_not_used_as_fallback(self):
        """ordinary_wage=0 은 None 취급 → average 사용."""
        payload = {
            "hire_date": "2022-01-01",
            "severance_date": "2023-01-01",
            "wage_records": [
                {"date": "2022-10-25", "amount": 3_000_000, "wage_type": "base"},
            ],
            "ordinary_wage_per_day": 0,
        }
        result = self._api.calculate_severance_preview(payload)
        self.assertEqual(result["severance_result"]["wage_used_reason"], "average")


if __name__ == "__main__":
    unittest.main()
