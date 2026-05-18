"""Tests: 근기법 60조 4항 — 출근률 80% 연차 감액 룰.

테스트 목록:
    1. 출근률 85% (>= 80%): 정상 15일 유지
    2. 출근률 75% (< 80%): anniversary 0, 월차만 (감액)
    3. 출근률 정확히 80%: 정상 (>= threshold → 감액 없음)
    4. 1년 미만 + attendance_ratio 높음: 월차 (기존과 동일, 감액 없음)
    5. 1년 미만 + attendance_ratio 낮음: 월차 (기존과 동일, 감액 없음)
    6. 5년차 + 출근률 80% 미만: anniversary 0 (17일 X, 월차만)
    7. 퇴사 + 80% 미만: employment_end_date 있고 감액 적용
    8. attendance_ratio < 0: ValueError
    9. attendance_ratio > 1: ValueError
    10. attendance_ratio = None: pass-through (기존 결과 그대로)
    11. attendance_ratio = True (bool): ValueError
    12. threshold=0.8 경계 확인 (0.7999... < 0.8 → 감액)
    13. Fiscal Year basis + 80% 미만: anniversary 감액
    14. 1년 정확히 + 80% 이상: 15일 (anniversary 정상)
"""

import datetime as dt
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "hrms" / "regional" / "south_korea" / "annual_leave_attendance_ratio.py"


def load_module():
    spec = importlib.util.spec_from_file_location("korea_annual_leave_attendance_ratio", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class KoreaAnnualLeaveAttendanceRatioTest(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()

    def _calc(self, **kwargs):
        return self.mod.calculate_with_attendance_ratio(**kwargs)

    # ------------------------------------------------------------------
    # 1. 출근률 85%: 정상 15일
    # ------------------------------------------------------------------
    def test_above_threshold_keeps_anniversary_entitlement(self):
        """출근률 0.85 (85%) → service_years=1, anniversary 15일 유지."""
        result = self._calc(
            hire_date=dt.date(2025, 1, 1),
            as_of_date=dt.date(2026, 1, 1),
            attendance_ratio=0.85,
        )

        self.assertFalse(result["below_threshold"])
        self.assertIsNone(result["adjustment_reason"])
        self.assertEqual(result["adjusted_annual_entitlement_days"], 15)
        self.assertEqual(result["adjusted_total_entitlement_days"], 15)
        self.assertEqual(result["base_entitlement"]["annual_entitlement_days"], 15)

    # ------------------------------------------------------------------
    # 2. 출근률 75%: anniversary 0, 월차만
    # ------------------------------------------------------------------
    def test_below_threshold_zeroes_anniversary_entitlement(self):
        """출근률 0.75 (75%) → service_years=1, anniversary 0으로 감액."""
        result = self._calc(
            hire_date=dt.date(2025, 1, 1),
            as_of_date=dt.date(2026, 1, 1),
            attendance_ratio=0.75,
        )

        self.assertTrue(result["below_threshold"])
        self.assertEqual(result["adjustment_reason"], "below_attendance_threshold")
        self.assertEqual(result["adjusted_annual_entitlement_days"], 0.0)
        # service_years=1 → monthly_accrual=0 → total=0
        self.assertEqual(result["adjusted_total_entitlement_days"], 0.0)
        # base entitlement은 그대로 보존 (원본 15일)
        self.assertEqual(result["base_entitlement"]["annual_entitlement_days"], 15)

    # ------------------------------------------------------------------
    # 3. 출근률 정확히 80%: 정상 (threshold 이상 → 감액 없음)
    # ------------------------------------------------------------------
    def test_exactly_at_threshold_is_not_below_threshold(self):
        """출근률 0.80 정확히 → below_threshold=False."""
        result = self._calc(
            hire_date=dt.date(2025, 1, 1),
            as_of_date=dt.date(2026, 1, 1),
            attendance_ratio=0.8,
        )

        self.assertFalse(result["below_threshold"])
        self.assertIsNone(result["adjustment_reason"])
        self.assertEqual(result["adjusted_annual_entitlement_days"], 15)
        self.assertEqual(result["adjusted_total_entitlement_days"], 15)

    # ------------------------------------------------------------------
    # 4. 1년 미만 + attendance_ratio 높음 (0.9): 월차, 감액 없음
    # ------------------------------------------------------------------
    def test_first_year_high_ratio_uses_monthly_accrual_only(self):
        """1년 미만 근로자는 attendance_ratio가 높아도 월차 체계."""
        result = self._calc(
            hire_date=dt.date(2026, 1, 1),
            as_of_date=dt.date(2026, 6, 1),
            attendance_ratio=0.9,
        )

        self.assertFalse(result["below_threshold"])
        self.assertIsNone(result["adjustment_reason"])
        # service_years=0 → monthly_accrual=5, annual=0
        self.assertEqual(result["base_entitlement"]["service_years"], 0)
        self.assertEqual(result["adjusted_annual_entitlement_days"], 0)
        self.assertEqual(result["adjusted_total_entitlement_days"], 5)

    # ------------------------------------------------------------------
    # 5. 1년 미만 + attendance_ratio 낮음 (0.5): 월차, 감액 없음
    # ------------------------------------------------------------------
    def test_first_year_low_ratio_still_monthly_accrual_only(self):
        """1년 미만은 attendance_ratio < threshold여도 anniversary 감액 불필요.
        법 조문: "1년 미만인 근로자에게는 1개월 개근 시 1일".
        below_threshold=True지만 service_years=0이므로 adjustment_reason=None.
        기존 월차(monthly_accrual)만 적용, 추가 감액 없음.
        """
        result = self._calc(
            hire_date=dt.date(2026, 1, 1),
            as_of_date=dt.date(2026, 9, 1),
            attendance_ratio=0.5,
        )

        # service_years=0이므로 감액 불필요 → adjustment_reason=None
        # below_threshold는 ratio(0.5) < threshold(0.8)이므로 True —
        # 단, 1년 미만 구간에서는 이미 monthly_accrual만 적용 중이라
        # anniversary 감액 조정 자체가 없으므로 adjustment_reason=None.
        # 하위 소비자는 below_threshold=True 단독으로 판단하지 않고
        # adjustment_reason을 함께 확인해야 함.
        self.assertTrue(result["below_threshold"])  # ratio 0.5 < threshold 0.8
        self.assertIsNone(result["adjustment_reason"])  # service_years=0 → 조정 없음
        self.assertEqual(result["base_entitlement"]["service_years"], 0)
        self.assertEqual(result["adjusted_annual_entitlement_days"], 0)
        # 8개월 완성 = 8일 (1월 1일 → 9월 1일 = 8개월 완성)
        self.assertEqual(result["adjusted_total_entitlement_days"], 8)

    # ------------------------------------------------------------------
    # 6. 5년차 + 출근률 80% 미만: anniversary(17일) 0으로 감액
    # ------------------------------------------------------------------
    def test_five_year_service_below_threshold_zeroes_anniversary(self):
        """5년 근속 (15+1=16일 또는 15+1=16 → 5년이면 15+2=17일).
        출근률 0.75 → anniversary 0으로 감액.

        계산: service_years=5 → additional=(5-1)//2=2 → 15+2=17일.
        """
        result = self._calc(
            hire_date=dt.date(2021, 1, 1),
            as_of_date=dt.date(2026, 1, 1),
            attendance_ratio=0.75,
        )

        self.assertEqual(result["base_entitlement"]["service_years"], 5)
        self.assertEqual(result["base_entitlement"]["annual_entitlement_days"], 17)
        self.assertTrue(result["below_threshold"])
        self.assertEqual(result["adjustment_reason"], "below_attendance_threshold")
        self.assertEqual(result["adjusted_annual_entitlement_days"], 0.0)
        self.assertEqual(result["adjusted_total_entitlement_days"], 0.0)

    # ------------------------------------------------------------------
    # 7. 퇴사 + 80% 미만: employment_end_date 적용 후 감액
    # ------------------------------------------------------------------
    def test_employment_end_date_with_below_threshold_applies_correctly(self):
        """퇴사일이 있고 출근률 < 80%인 경우 employment_end_date를 반영한 뒤 감액."""
        result = self._calc(
            hire_date=dt.date(2024, 1, 1),
            as_of_date=dt.date(2026, 6, 30),
            attendance_ratio=0.75,
            employment_end_date=dt.date(2026, 6, 30),
        )

        # service_years=2, annual=15 (2년, additional=0)
        self.assertEqual(result["base_entitlement"]["service_years"], 2)
        self.assertTrue(result["below_threshold"])
        self.assertEqual(result["adjusted_annual_entitlement_days"], 0.0)
        self.assertEqual(result["adjusted_total_entitlement_days"], 0.0)
        self.assertEqual(result["adjustment_reason"], "below_attendance_threshold")

    # ------------------------------------------------------------------
    # 8. attendance_ratio < 0: ValueError
    # ------------------------------------------------------------------
    def test_negative_attendance_ratio_raises_value_error(self):
        with self.assertRaises(ValueError):
            self._calc(
                hire_date=dt.date(2025, 1, 1),
                as_of_date=dt.date(2026, 1, 1),
                attendance_ratio=-0.1,
            )

    # ------------------------------------------------------------------
    # 9. attendance_ratio > 1: ValueError
    # ------------------------------------------------------------------
    def test_attendance_ratio_greater_than_one_raises_value_error(self):
        with self.assertRaises(ValueError):
            self._calc(
                hire_date=dt.date(2025, 1, 1),
                as_of_date=dt.date(2026, 1, 1),
                attendance_ratio=1.01,
            )

    # ------------------------------------------------------------------
    # 10. attendance_ratio = None: pass-through
    # ------------------------------------------------------------------
    def test_none_attendance_ratio_returns_passthrough(self):
        """attendance_ratio=None → 조정 없음, 기존 calculate_annual_leave_entitlement 결과."""
        result = self._calc(
            hire_date=dt.date(2025, 1, 1),
            as_of_date=dt.date(2026, 1, 1),
            attendance_ratio=None,
        )

        self.assertIsNone(result["attendance_ratio"])
        self.assertFalse(result["below_threshold"])
        self.assertIsNone(result["adjustment_reason"])
        # 기존 계산 그대로
        base = result["base_entitlement"]
        self.assertEqual(result["adjusted_annual_entitlement_days"], base["annual_entitlement_days"])
        self.assertEqual(result["adjusted_total_entitlement_days"], base["total_entitlement_days"])

    # ------------------------------------------------------------------
    # 11. attendance_ratio = True (bool): ValueError
    # ------------------------------------------------------------------
    def test_bool_attendance_ratio_raises_value_error(self):
        """bool은 float의 서브클래스이지만 명시적으로 거부."""
        with self.assertRaises(ValueError):
            self._calc(
                hire_date=dt.date(2025, 1, 1),
                as_of_date=dt.date(2026, 1, 1),
                attendance_ratio=True,
            )

    # ------------------------------------------------------------------
    # 12. 경계값: 0.7999... < 0.8 → 감액
    # ------------------------------------------------------------------
    def test_just_below_threshold_is_reduced(self):
        """0.7999... < 0.8 → below_threshold=True."""
        result = self._calc(
            hire_date=dt.date(2025, 1, 1),
            as_of_date=dt.date(2026, 1, 1),
            attendance_ratio=0.7999,
        )

        self.assertTrue(result["below_threshold"])
        self.assertEqual(result["adjustment_reason"], "below_attendance_threshold")
        self.assertEqual(result["adjusted_annual_entitlement_days"], 0.0)

    # ------------------------------------------------------------------
    # 13. Fiscal Year basis + 80% 미만: anniversary 감액
    # ------------------------------------------------------------------
    def test_fiscal_year_basis_below_threshold_zeroes_annual_entitlement(self):
        """Fiscal Year 기준 + 출근률 75% → anniversary 감액.
        hire_date=2024-01-01, as_of=2026-01-01 → service_years=2, annual=15.
        """
        result = self._calc(
            hire_date=dt.date(2024, 1, 1),
            as_of_date=dt.date(2026, 1, 1),
            attendance_ratio=0.75,
            basis="Fiscal Year",
        )

        self.assertTrue(result["below_threshold"])
        self.assertEqual(result["adjusted_annual_entitlement_days"], 0.0)
        self.assertEqual(result["adjustment_reason"], "below_attendance_threshold")

    # ------------------------------------------------------------------
    # 14. 1년 정확히 + 80% 이상: 15일
    # ------------------------------------------------------------------
    def test_exactly_one_year_above_threshold_grants_fifteen_days(self):
        result = self._calc(
            hire_date=dt.date(2025, 5, 1),
            as_of_date=dt.date(2026, 5, 1),
            attendance_ratio=0.82,
        )

        self.assertEqual(result["base_entitlement"]["service_years"], 1)
        self.assertFalse(result["below_threshold"])
        self.assertEqual(result["adjusted_annual_entitlement_days"], 15)
        self.assertEqual(result["adjusted_total_entitlement_days"], 15)

    # ------------------------------------------------------------------
    # 추가: return dict 구조 검증
    # ------------------------------------------------------------------
    def test_return_dict_has_all_required_keys(self):
        """반환 dict에 spec 정의 키가 모두 존재해야 한다."""
        result = self._calc(
            hire_date=dt.date(2025, 1, 1),
            as_of_date=dt.date(2026, 1, 1),
            attendance_ratio=0.8,
        )

        required_keys = {
            "base_entitlement",
            "attendance_ratio",
            "threshold",
            "below_threshold",
            "adjusted_annual_entitlement_days",
            "adjusted_total_entitlement_days",
            "adjustment_reason",
        }
        self.assertEqual(required_keys, required_keys & set(result.keys()))

    def test_base_entitlement_dates_are_serialized_as_strings(self):
        """base_entitlement의 날짜 필드는 ISO 문자열로 직렬화되어야 한다."""
        result = self._calc(
            hire_date=dt.date(2025, 1, 1),
            as_of_date=dt.date(2026, 1, 1),
            attendance_ratio=0.8,
        )
        base = result["base_entitlement"]
        for key in ("hire_date", "as_of_date", "period_start", "period_end"):
            self.assertIsInstance(base[key], str, f"{key} should be a string")

    # ------------------------------------------------------------------
    # 추가: 출근률 0.0 (0%): 유효하지만 감액
    # ------------------------------------------------------------------
    def test_zero_attendance_ratio_is_valid_and_below_threshold(self):
        result = self._calc(
            hire_date=dt.date(2025, 1, 1),
            as_of_date=dt.date(2026, 1, 1),
            attendance_ratio=0.0,
        )
        self.assertTrue(result["below_threshold"])
        self.assertEqual(result["adjusted_annual_entitlement_days"], 0.0)

    # ------------------------------------------------------------------
    # 추가: 출근률 1.0 (100%): 정상
    # ------------------------------------------------------------------
    def test_full_attendance_ratio_is_valid_and_not_below_threshold(self):
        result = self._calc(
            hire_date=dt.date(2025, 1, 1),
            as_of_date=dt.date(2026, 1, 1),
            attendance_ratio=1.0,
        )
        self.assertFalse(result["below_threshold"])
        self.assertEqual(result["adjusted_annual_entitlement_days"], 15)


if __name__ == "__main__":
    unittest.main()
