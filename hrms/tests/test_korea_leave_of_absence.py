"""테스트: 한국 휴직 처리 코어 및 API 래퍼.

코어 모듈(leave_of_absence.py)은 framework-free이므로 frappe 없이 직접 import.
API 래퍼(korea_leave_of_absence.py)는 FakeFrappeModule을 사용.

테스트 시나리오:
  - 육아휴직 18개월 신청 + 4대보험 유지 (사업주 부담)
  - 산전·산후 90일 + 유급
  - 무급 휴직 + 국민연금 본인 부담 납부예외
  - 휴직 기간 평균임금 산정 제외 (근기법 시행령 2조)
  - 육아휴직급여 1-3월 80% / 4-6월 50% 정확
  - 승인 흐름: human_approved=True 필수
  - API 래퍼 입력 검증
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import pathlib
import sys
import types
import unittest

# ---------------------------------------------------------------------------
# 코어 모듈 직접 import (framework-free)
# ---------------------------------------------------------------------------

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_CORE_PATH = _REPO_ROOT / "hrms" / "regional" / "south_korea" / "leave_of_absence.py"
_API_PATH = _REPO_ROOT / "hrms" / "api" / "korea_leave_of_absence.py"


def _load_core():
    spec = importlib.util.spec_from_file_location("leave_of_absence_core", _CORE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Frappe 가짜 모듈 (API 래퍼 테스트용)
# ---------------------------------------------------------------------------


class FakeFrappeError(Exception):
    pass


class FakeFrappeModule(types.SimpleNamespace):
    def __init__(self):
        super().__init__()
        self.whitelist = lambda *args, **kwargs: (lambda fn: fn)
        self.throw = self._throw
        self.local = types.SimpleNamespace(form_dict={}, request=None)

    def _throw(self, message, exc=None):
        raise FakeFrappeError(message)


def _load_api(fake_frappe):
    """API 래퍼를 fake frappe로 로드."""
    sys.modules["frappe"] = fake_frappe

    # 코어 모듈을 sys.modules에 등록 (API 래퍼가 import함)
    core_spec = importlib.util.spec_from_file_location(
        "hrms.regional.south_korea.leave_of_absence", _CORE_PATH
    )
    core_mod = importlib.util.module_from_spec(core_spec)
    sys.modules["hrms.regional.south_korea.leave_of_absence"] = core_mod
    sys.modules["hrms.regional.south_korea"] = types.ModuleType("hrms.regional.south_korea")
    sys.modules["hrms.regional"] = types.ModuleType("hrms.regional")
    sys.modules["hrms"] = types.ModuleType("hrms")
    core_spec.loader.exec_module(core_mod)

    api_spec = importlib.util.spec_from_file_location("korea_leave_of_absence_api", _API_PATH)
    api_mod = importlib.util.module_from_spec(api_spec)
    api_spec.loader.exec_module(api_mod)
    return api_mod


# ===========================================================================
# 1. 코어 모듈 테스트 (framework-free)
# ===========================================================================


class TestLeaveOfAbsenceCore(unittest.TestCase):
    """hrms/regional/south_korea/leave_of_absence.py 직접 테스트."""

    def setUp(self):
        self.core = _load_core()

    # -------------------------------------------------------------------
    # request_leave_of_absence
    # -------------------------------------------------------------------

    def test_childcare_request_18months_returns_pending(self):
        """육아휴직 18개월 신청 → pending 상태, 법적 근거 포함."""
        start = dt.date(2026, 1, 1)
        end = dt.date(2027, 6, 30)  # 18개월
        result = self.core.request_leave_of_absence(
            employee="EMP-0001",
            leave_type="childcare",
            start_date=start,
            end_date=end,
            reason="첫째 아이 육아",
        )
        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["leave_type"], "childcare")
        self.assertEqual(result["leave_type_name"], "육아휴직")
        self.assertIn("남녀고용평등법", result["law_basis"])
        self.assertIsNotNone(result["request_id"])
        self.assertIn("LOA-", result["request_id"])

    def test_childcare_request_human_approved_true_returns_approved(self):
        """human_approved=True 이면 즉시 approved."""
        result = self.core.request_leave_of_absence(
            employee="EMP-0001",
            leave_type="childcare",
            start_date=dt.date(2026, 1, 1),
            end_date=dt.date(2026, 6, 30),
            reason="육아",
            human_approved=True,
        )
        self.assertEqual(result["status"], "approved")

    def test_maternity_90days_paid(self):
        """산전·산후 90일 유급 휴가 신청."""
        start = dt.date(2026, 3, 1)
        end = dt.date(2026, 5, 29)  # 90일
        result = self.core.request_leave_of_absence(
            employee="EMP-0002",
            leave_type="maternity",
            start_date=start,
            end_date=end,
            reason="산전·산후 휴가",
        )
        self.assertEqual(result["leave_type"], "maternity")
        self.assertEqual(result["leave_type_name"], "산전·산후 휴가")
        self.assertIn("근기법", result["law_basis"])
        self.assertEqual(result["duration_days"], 90)

    def test_maternity_exceeds_90days_raises(self):
        """91일 초과 산전·산후 → ValueError."""
        with self.assertRaises(ValueError) as ctx:
            self.core.request_leave_of_absence(
                employee="EMP-0002",
                leave_type="maternity",
                start_date=dt.date(2026, 1, 1),
                end_date=dt.date(2026, 4, 2),  # 91일
                reason="산전·산후",
            )
        self.assertIn("90", str(ctx.exception))

    def test_end_date_before_start_date_raises(self):
        """종료일이 시작일보다 이르면 ValueError."""
        with self.assertRaises(ValueError):
            self.core.request_leave_of_absence(
                employee="EMP-0001",
                leave_type="personal",
                start_date=dt.date(2026, 5, 10),
                end_date=dt.date(2026, 5, 9),
                reason="테스트",
            )

    def test_invalid_leave_type_raises(self):
        """존재하지 않는 휴직 유형 → ValueError."""
        with self.assertRaises(ValueError):
            self.core.request_leave_of_absence(
                employee="EMP-0001",
                leave_type="invalid_type",
                start_date=dt.date(2026, 1, 1),
                end_date=None,
                reason="테스트",
            )

    def test_empty_employee_raises(self):
        """빈 직원 ID → ValueError."""
        with self.assertRaises(ValueError):
            self.core.request_leave_of_absence(
                employee="",
                leave_type="personal",
                start_date=dt.date(2026, 1, 1),
                end_date=None,
                reason="테스트",
            )

    def test_open_ended_leave_allowed(self):
        """end_date=None (미정) 허용."""
        result = self.core.request_leave_of_absence(
            employee="EMP-0001",
            leave_type="personal",
            start_date=dt.date(2026, 1, 1),
            end_date=None,
            reason="개인 사유",
        )
        self.assertIsNone(result["end_date"])
        self.assertIsNone(result["duration_days"])

    # -------------------------------------------------------------------
    # approve_leave_of_absence
    # -------------------------------------------------------------------

    def test_approve_with_human_approved_true(self):
        """human_approved=True → approved 반환."""
        result = self.core.approve_leave_of_absence(
            request_id="LOA-ABCD1234",
            approver="HR-Manager",
            human_approved=True,
        )
        self.assertEqual(result["status"], "approved")
        self.assertEqual(result["request_id"], "LOA-ABCD1234")
        self.assertEqual(result["approver"], "HR-Manager")
        self.assertIn("approved_at", result)

    def test_approve_with_human_approved_false_raises(self):
        """human_approved=False → ValueError (승인 불가)."""
        with self.assertRaises(ValueError) as ctx:
            self.core.approve_leave_of_absence(
                request_id="LOA-ABCD1234",
                approver="HR-Manager",
                human_approved=False,
            )
        self.assertIn("human_approved", str(ctx.exception))

    # -------------------------------------------------------------------
    # calculate_insurance_during_leave
    # -------------------------------------------------------------------

    def test_childcare_insurance_employer_pension_continues(self):
        """육아휴직: 국민연금 사업주 부담 계속, 본인 납부예외."""
        result = self.core.calculate_insurance_during_leave(
            leave_type="childcare",
            leave_start_date=dt.date(2026, 1, 1),
            leave_end_date=dt.date(2026, 6, 30),
            monthly_base_salary=3_000_000,
        )
        self.assertTrue(result["pension_continues"])
        # 사업주 부담 4.5% = 135,000원
        # 3,000,000 × 4.75% (2026 연금개혁, statutory_2026 단일소스) = 142,500
        self.assertEqual(result["pension_employer_payment"], 142_500)
        self.assertTrue(result["pension_employee_deferred"])
        self.assertTrue(result["health_insurance_continues"])
        self.assertTrue(result["employment_insurance_continues"])
        self.assertTrue(result["industrial_accident_insurance_continues"])

    def test_personal_unpaid_pension_not_continues(self):
        """무급휴직: 국민연금 납부예외 (pension_continues=False, employer_payment=0)."""
        result = self.core.calculate_insurance_during_leave(
            leave_type="personal",
            leave_start_date=dt.date(2026, 2, 1),
            leave_end_date=dt.date(2026, 4, 30),
            monthly_base_salary=2_500_000,
        )
        self.assertFalse(result["pension_continues"])
        self.assertEqual(result["pension_employer_payment"], 0.0)
        self.assertTrue(result["pension_employee_deferred"])
        # 건강보험은 직장가입자 유지
        self.assertTrue(result["health_insurance_continues"])

    def test_sick_unpaid_pension_deferred(self):
        """무급 병가: 국민연금 납부예외 신청 가능."""
        result = self.core.calculate_insurance_during_leave(
            leave_type="sick_unpaid",
            leave_start_date=dt.date(2026, 3, 1),
            leave_end_date=dt.date(2026, 5, 31),
            monthly_base_salary=2_000_000,
        )
        self.assertFalse(result["pension_continues"])
        self.assertTrue(result["pension_employee_deferred"])
        self.assertTrue(result["health_insurance_continues"])

    def test_maternity_full_insurance_maintained(self):
        """산전·산후: 4대보험 모두 유지."""
        result = self.core.calculate_insurance_during_leave(
            leave_type="maternity",
            leave_start_date=dt.date(2026, 3, 1),
            leave_end_date=dt.date(2026, 5, 29),
            monthly_base_salary=3_500_000,
        )
        self.assertTrue(result["pension_continues"])
        self.assertGreater(result["pension_employer_payment"], 0)
        self.assertFalse(result["pension_employee_deferred"])
        self.assertTrue(result["health_insurance_continues"])
        self.assertTrue(result["employment_insurance_continues"])

    def test_negative_salary_raises(self):
        """음수 임금 → ValueError."""
        with self.assertRaises(ValueError):
            self.core.calculate_insurance_during_leave(
                leave_type="childcare",
                leave_start_date=dt.date(2026, 1, 1),
                leave_end_date=dt.date(2026, 6, 30),
                monthly_base_salary=-1_000,
            )

    # -------------------------------------------------------------------
    # calculate_childcare_benefit
    # -------------------------------------------------------------------

    def test_childcare_benefit_month1_80_percent_with_cap(self):
        """1개월: 80%, 상한 250만원."""
        # 통상임금 3,500,000 → 80% = 2,800,000 → 상한 2,500,000
        result = self.core.calculate_childcare_benefit(
            monthly_base_salary=3_500_000,
            leave_month_index=1,
        )
        self.assertEqual(result["rate"], 0.80)
        self.assertEqual(result["cap"], 2_500_000)
        self.assertEqual(result["floor"], 700_000)
        self.assertEqual(result["benefit_amount"], 2_500_000)

    def test_childcare_benefit_month2_80_percent_below_cap(self):
        """2개월: 80%, 상한 미달 → gross 지급."""
        # 통상임금 2,000,000 → 80% = 1,600,000 → 상한 2,500,000 미달 → 1,600,000
        result = self.core.calculate_childcare_benefit(
            monthly_base_salary=2_000_000,
            leave_month_index=2,
        )
        self.assertEqual(result["rate"], 0.80)
        self.assertEqual(result["benefit_amount"], 1_600_000)

    def test_childcare_benefit_month3_80_percent_floor_applied(self):
        """3개월: 80%, 하한 70만원 적용."""
        # 통상임금 800,000 → 80% = 640,000 < 700,000 → 700,000
        result = self.core.calculate_childcare_benefit(
            monthly_base_salary=800_000,
            leave_month_index=3,
        )
        self.assertEqual(result["rate"], 0.80)
        self.assertEqual(result["benefit_amount"], 700_000)

    def test_childcare_benefit_month4_50_percent_cap200(self):
        """4개월: 50%, 상한 200만원."""
        # 통상임금 4,500,000 → 50% = 2,250,000 → 상한 2,000,000
        result = self.core.calculate_childcare_benefit(
            monthly_base_salary=4_500_000,
            leave_month_index=4,
        )
        self.assertEqual(result["rate"], 0.50)
        self.assertEqual(result["cap"], 2_000_000)
        self.assertEqual(result["benefit_amount"], 2_000_000)

    def test_childcare_benefit_month6_50_percent(self):
        """6개월: 4-6 구간 50%."""
        result = self.core.calculate_childcare_benefit(
            monthly_base_salary=3_000_000,
            leave_month_index=6,
        )
        self.assertEqual(result["rate"], 0.50)
        self.assertEqual(result["cap"], 2_000_000)

    def test_childcare_benefit_month7_50_percent_cap160(self):
        """7개월: 50%, 상한 160만원."""
        result = self.core.calculate_childcare_benefit(
            monthly_base_salary=4_000_000,
            leave_month_index=7,
        )
        self.assertEqual(result["rate"], 0.50)
        self.assertEqual(result["cap"], 1_600_000)
        self.assertEqual(result["benefit_amount"], 1_600_000)

    def test_childcare_benefit_month12_50_percent_cap160(self):
        """12개월: 7-12 구간 끝, 상한 160만원."""
        result = self.core.calculate_childcare_benefit(
            monthly_base_salary=4_000_000,
            leave_month_index=12,
        )
        self.assertEqual(result["cap"], 1_600_000)
        self.assertEqual(result["benefit_amount"], 1_600_000)

    def test_childcare_benefit_month13_2026_extension(self):
        """13개월: 2026년 확대 (13-18개월 구간), 상한 160만원."""
        result = self.core.calculate_childcare_benefit(
            monthly_base_salary=4_000_000,
            leave_month_index=13,
        )
        self.assertEqual(result["rate"], 0.50)
        self.assertEqual(result["cap"], 1_600_000)
        self.assertEqual(result["benefit_amount"], 1_600_000)

    def test_childcare_benefit_month18_2026_extension(self):
        """18개월: 2026년 확대 최대치."""
        result = self.core.calculate_childcare_benefit(
            monthly_base_salary=2_400_000,
            leave_month_index=18,
        )
        self.assertEqual(result["rate"], 0.50)
        # 2,400,000 × 50% = 1,200,000 ≤ 1,600,000
        self.assertEqual(result["benefit_amount"], 1_200_000)

    def test_childcare_benefit_month19_raises(self):
        """19개월: 최대 18개월 초과 → ValueError."""
        with self.assertRaises(ValueError) as ctx:
            self.core.calculate_childcare_benefit(
                monthly_base_salary=3_000_000,
                leave_month_index=19,
            )
        self.assertIn("18", str(ctx.exception))

    def test_childcare_benefit_month0_raises(self):
        """0개월: 1 미만 → ValueError."""
        with self.assertRaises(ValueError):
            self.core.calculate_childcare_benefit(
                monthly_base_salary=3_000_000,
                leave_month_index=0,
            )

    # -------------------------------------------------------------------
    # adjust_average_wage_for_leave
    # -------------------------------------------------------------------

    def test_average_wage_excludes_leave_period(self):
        """평균임금 산정: 퇴직 전 3개월 중 휴직 기간 제외."""
        # 2026-02-01 ~ 2026-04-30 (89일)
        # 휴직: 2026-03-01 ~ 2026-03-31 (31일)
        result = self.core.adjust_average_wage_for_leave(
            severance_calculation_period=(dt.date(2026, 2, 1), dt.date(2026, 4, 30)),
            leave_periods=[(dt.date(2026, 3, 1), dt.date(2026, 3, 31))],
        )
        self.assertEqual(result["original_days"], 89)
        self.assertEqual(result["excluded_leave_days"], 31)
        self.assertEqual(result["effective_days"], 58)
        self.assertIn("근로기준법", result["law_basis"])
        self.assertEqual(len(result["excluded_periods"]), 1)
        self.assertEqual(result["excluded_periods"][0]["overlap_days"], 31)

    def test_average_wage_leave_outside_period_not_excluded(self):
        """산정 기간 밖의 휴직은 제외되지 않음."""
        result = self.core.adjust_average_wage_for_leave(
            severance_calculation_period=(dt.date(2026, 2, 1), dt.date(2026, 4, 30)),
            leave_periods=[
                (dt.date(2025, 10, 1), dt.date(2025, 12, 31)),  # 기간 밖
            ],
        )
        self.assertEqual(result["excluded_leave_days"], 0)
        self.assertEqual(result["effective_days"], result["original_days"])
        self.assertEqual(len(result["excluded_periods"]), 0)

    def test_average_wage_multiple_leave_periods(self):
        """복수 휴직 기간 합산 제외."""
        result = self.core.adjust_average_wage_for_leave(
            severance_calculation_period=(dt.date(2026, 1, 1), dt.date(2026, 3, 31)),
            leave_periods=[
                (dt.date(2026, 1, 5), dt.date(2026, 1, 14)),  # 10일
                (dt.date(2026, 2, 1), dt.date(2026, 2, 10)),  # 10일
            ],
        )
        self.assertEqual(result["excluded_leave_days"], 20)
        self.assertEqual(result["effective_days"], result["original_days"] - 20)

    def test_average_wage_empty_leave_periods(self):
        """휴직 기간 없을 때 제외 없음."""
        result = self.core.adjust_average_wage_for_leave(
            severance_calculation_period=(dt.date(2026, 1, 1), dt.date(2026, 3, 31)),
            leave_periods=[],
        )
        self.assertEqual(result["excluded_leave_days"], 0)
        self.assertEqual(result["effective_days"], result["original_days"])

    def test_average_wage_invalid_period_raises(self):
        """종료일 < 시작일 → ValueError."""
        with self.assertRaises(ValueError):
            self.core.adjust_average_wage_for_leave(
                severance_calculation_period=(dt.date(2026, 4, 30), dt.date(2026, 1, 1)),
                leave_periods=[],
            )


# ===========================================================================
# 2. API 래퍼 테스트 (FakeFrappeModule 사용)
# ===========================================================================


class TestLeaveOfAbsenceApi(unittest.TestCase):
    """hrms/api/korea_leave_of_absence.py API 래퍼 테스트."""

    def setUp(self):
        self.fake_frappe = FakeFrappeModule()
        self.api = _load_api(self.fake_frappe)

    def tearDown(self):
        # sys.modules 정리
        for key in list(sys.modules):
            if key in {
                "frappe",
                "hrms",
                "hrms.regional",
                "hrms.regional.south_korea",
                "hrms.regional.south_korea.leave_of_absence",
                "korea_leave_of_absence_api",
            }:
                sys.modules.pop(key, None)

    def test_api_request_leave_returns_request_id(self):
        """API 휴직 신청 → request_id 반환."""
        result = self.api.api_request_leave_of_absence(
            payload={
                "employee": "EMP-0001",
                "leave_type": "childcare",
                "start_date": "2026-01-01",
                "end_date": "2026-06-30",
                "reason": "육아",
            }
        )
        self.assertIn("request_id", result)
        self.assertEqual(result["leave_type"], "childcare")
        self.assertEqual(result["status"], "pending")

    def test_api_request_leave_missing_required_field_throws(self):
        """필수 필드 누락 → frappe.throw (FakeFrappeError)."""
        with self.assertRaises(FakeFrappeError):
            self.api.api_request_leave_of_absence(
                payload={
                    "leave_type": "childcare",
                    "start_date": "2026-01-01",
                    # "employee" 누락
                    "reason": "육아",
                }
            )

    def test_api_request_leave_unknown_field_throws(self):
        """미지원 필드 포함 → frappe.throw."""
        with self.assertRaises(FakeFrappeError):
            self.api.api_request_leave_of_absence(
                payload={
                    "employee": "EMP-0001",
                    "leave_type": "childcare",
                    "start_date": "2026-01-01",
                    "reason": "육아",
                    "unknown_field": "x",
                }
            )

    def test_api_request_leave_invalid_leave_type_throws(self):
        """잘못된 leave_type → frappe.throw (ValueError → throw 변환)."""
        with self.assertRaises(FakeFrappeError):
            self.api.api_request_leave_of_absence(
                payload={
                    "employee": "EMP-0001",
                    "leave_type": "sabbatical",
                    "start_date": "2026-01-01",
                    "reason": "학습",
                }
            )

    def test_api_approve_human_approved_true(self):
        """API 승인: human_approved=True → approved."""
        result = self.api.api_approve_leave_of_absence(
            payload={
                "request_id": "LOA-ABCD1234",
                "approver": "HR-Manager",
                "human_approved": True,
            }
        )
        self.assertEqual(result["status"], "approved")

    def test_api_approve_human_approved_false_throws(self):
        """API 승인: human_approved=False → frappe.throw."""
        with self.assertRaises(FakeFrappeError):
            self.api.api_approve_leave_of_absence(
                payload={
                    "request_id": "LOA-ABCD1234",
                    "approver": "HR-Manager",
                    "human_approved": False,
                }
            )

    def test_api_calculate_insurance_childcare(self):
        """API 보험 계산: 육아휴직 → 사업주 부담 반환."""
        result = self.api.api_calculate_insurance_during_leave(
            payload={
                "leave_type": "childcare",
                "leave_start_date": "2026-01-01",
                "leave_end_date": "2026-06-30",
                "monthly_base_salary": 3000000,
            }
        )
        self.assertTrue(result["pension_continues"])
        # 3,000,000 × 4.75% (2026 연금개혁, statutory_2026 단일소스) = 142,500
        self.assertEqual(result["pension_employer_payment"], 142_500)
        self.assertTrue(result["pension_employee_deferred"])

    def test_api_calculate_childcare_benefit_month1(self):
        """API 육아휴직급여: 1개월, 80%, 상한 250만원."""
        result = self.api.api_calculate_childcare_benefit(
            payload={
                "monthly_base_salary": 4000000,
                "leave_month_index": 1,
            }
        )
        self.assertEqual(result["rate"], 0.80)
        self.assertEqual(result["benefit_amount"], 2_500_000)

    def test_api_calculate_childcare_benefit_month5(self):
        """API 육아휴직급여: 5개월, 50%, 상한 200만원."""
        result = self.api.api_calculate_childcare_benefit(
            payload={
                "monthly_base_salary": 5000000,
                "leave_month_index": 5,
            }
        )
        self.assertEqual(result["rate"], 0.50)
        self.assertEqual(result["benefit_amount"], 2_000_000)

    def test_api_calculate_childcare_benefit_month19_throws(self):
        """API 육아휴직급여: 19개월 → frappe.throw."""
        with self.assertRaises(FakeFrappeError):
            self.api.api_calculate_childcare_benefit(
                payload={
                    "monthly_base_salary": 3000000,
                    "leave_month_index": 19,
                }
            )

    def test_api_adjust_average_wage(self):
        """API 평균임금 조정: 휴직 기간 제외."""
        result = self.api.api_adjust_average_wage_for_leave(
            payload={
                "severance_calculation_period": {
                    "start_date": "2026-02-01",
                    "end_date": "2026-04-30",
                },
                "leave_periods": [
                    {"start_date": "2026-03-01", "end_date": "2026-03-31"},
                ],
            }
        )
        self.assertEqual(result["excluded_leave_days"], 31)
        self.assertEqual(result["effective_days"], 58)
        self.assertEqual(len(result["excluded_periods"]), 1)

    def test_api_adjust_average_wage_missing_period_throws(self):
        """API 평균임금 조정: severance_calculation_period 누락 → throw."""
        with self.assertRaises(FakeFrappeError):
            self.api.api_adjust_average_wage_for_leave(
                payload={
                    "leave_periods": [],
                    # severance_calculation_period 누락
                }
            )

    def test_api_adjust_average_wage_invalid_leave_periods_type_throws(self):
        """API 평균임금 조정: leave_periods가 list 아님 → throw."""
        with self.assertRaises(FakeFrappeError):
            self.api.api_adjust_average_wage_for_leave(
                payload={
                    "severance_calculation_period": {
                        "start_date": "2026-02-01",
                        "end_date": "2026-04-30",
                    },
                    "leave_periods": "not-a-list",
                }
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
