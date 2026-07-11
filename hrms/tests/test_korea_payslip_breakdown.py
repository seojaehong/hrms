# -*- coding: utf-8 -*-
"""임금명세서 산정내역 분해 생성기(payslip_breakdown.py) 테스트.

근로기준법 §48②(임금명세서) 요건 — 구성항목별 계산방법 문자열 필수·공제내역·실지급액.
개인 스킬 「명세서생성」의 분해 사상을 엔진화한 신규 조립 모듈 검증.

framework-free: hrms/__init__.py가 frappe를 import하므로 spec_from_file_location으로
직접 로드한다 (hourly_wage.py 컨벤션과 동일). 가상 인물 예시만 사용 — 고객명 금지.
실행: python3 hrms/tests/test_korea_payslip_breakdown.py
"""
from __future__ import annotations

import importlib.util
import pathlib
import unittest
from decimal import Decimal

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_SK_DIR = _REPO_ROOT / "hrms" / "regional" / "south_korea"

_spec = importlib.util.spec_from_file_location(
    "payslip_breakdown", _SK_DIR / "payslip_breakdown.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

build_payslip_breakdown = _mod.build_payslip_breakdown
render_payslip_markdown = _mod.render_payslip_markdown

_hourly_spec = importlib.util.spec_from_file_location("hourly_wage", _SK_DIR / "hourly_wage.py")
_hourly = importlib.util.module_from_spec(_hourly_spec)
_hourly_spec.loader.exec_module(_hourly)

_statutory_spec = importlib.util.spec_from_file_location(
    "statutory_2026", _SK_DIR / "statutory_2026.py"
)
_statutory = importlib.util.module_from_spec(_statutory_spec)
_statutory_spec.loader.exec_module(_statutory)


class TestMonthlyBreakdown(unittest.TestCase):
    """월급제(정액) 경로 — 기본급은 209h 고정분모로 통상시급 환산 basis만 표기."""

    def _build(self, **overrides):
        params = dict(
            employee="김철수",
            period="2026-07",
            payment_date="2026-08-10",
            wage_type="monthly",
            base_salary=2156880,  # 209h x 10,320원 (기존 엔진 테스트 픽스처와 정렬)
        )
        params.update(overrides)
        return build_payslip_breakdown(**params)

    def test_base_salary_line_has_basis_with_209h_and_rate(self):
        result = self._build()
        base_line = result["earnings"][0]
        self.assertEqual(base_line["label"], "기본급")
        self.assertEqual(base_line["amount"], 2156880)
        self.assertIn("209h", base_line["basis"])
        self.assertIn("10,320", base_line["basis"])

    def test_gross_pay_equals_sum_of_earnings(self):
        result = self._build()
        self.assertEqual(result["gross_pay"], sum(l["amount"] for l in result["earnings"]))

    def test_monthly_has_no_separate_weekly_holiday_line(self):
        # 월급제는 209h 고정급에 주휴가 이미 포함 — 별도 라인 없음.
        result = self._build()
        labels = [l["label"] for l in result["earnings"]]
        self.assertNotIn("주휴수당", labels)

    def test_overtime_line_uses_15x_multiplier(self):
        result = self._build(overtime_hours=10)
        ot = next(l for l in result["earnings"] if l["label"] == "연장근로수당")
        self.assertEqual(ot["amount"], round(10 * 10320 * 1.5))
        self.assertIn("10h", ot["basis"])
        self.assertIn("1.5", ot["basis"])

    def test_night_line_uses_half_addend(self):
        result = self._build(night_hours=8)
        night = next(l for l in result["earnings"] if l["label"] == "야간근로수당")
        self.assertEqual(night["amount"], round(8 * 10320 * 0.5))

    def test_holiday_work_line_uses_15x_multiplier(self):
        result = self._build(holiday_work_hours=8)
        hol = next(l for l in result["earnings"] if l["label"] == "휴일근로수당")
        self.assertEqual(hol["amount"], round(8 * 10320 * 1.5))

    def test_annual_leave_line_uses_1x(self):
        result = self._build(annual_leave_hours=8)
        leave = next(l for l in result["earnings"] if l["label"] == "연차수당")
        self.assertEqual(leave["amount"], 8 * 10320)

    def test_zero_hour_buckets_produce_no_line(self):
        result = self._build()
        labels = [l["label"] for l in result["earnings"]]
        self.assertEqual(labels, ["기본급"])

    def test_deductions_match_statutory_2026_directly(self):
        result = self._build()
        expected = _statutory.calculate_all_statutory(monthly_base=2156880.0, monthly_taxable_income=2156880.0)
        pension = next(l for l in result["deductions"] if l["label"] == "국민연금")
        health = next(l for l in result["deductions"] if l["label"] == "건강보험")
        income_tax = next(l for l in result["deductions"] if l["label"] == "소득세")
        self.assertEqual(pension["amount"], expected["pension"]["employee"])
        self.assertEqual(health["amount"], expected["health"]["health_employee"])
        self.assertEqual(income_tax["amount"], expected["income_tax"]["income_tax"])

    def test_net_pay_is_gross_minus_total_deductions(self):
        result = self._build()
        self.assertEqual(result["net_pay"], result["gross_pay"] - result["total_deductions"])

    def test_all_deduction_lines_have_basis(self):
        result = self._build()
        for line in result["deductions"]:
            self.assertTrue(line["basis"])

    def test_compliant_when_all_earnings_have_basis(self):
        result = self._build()
        self.assertTrue(result["compliance"]["compliant"])
        self.assertEqual(result["compliance"]["missing_basis_labels"], [])


class TestHourlyBreakdown(unittest.TestCase):
    """시급제 경로 — 주휴수당 별도 라인 + hourly_wage.py 단일 소스로 교차검증."""

    def _build(self, **overrides):
        params = dict(
            employee="이영희",
            period="2026-07",
            payment_date="2026-08-10",
            wage_type="hourly",
            hourly_rate=10320,
            regular_hours=160,
            contracted_weekly_hours=40,
        )
        params.update(overrides)
        return build_payslip_breakdown(**params)

    def test_base_line_from_regular_hours(self):
        result = self._build()
        base = result["earnings"][0]
        self.assertEqual(base["label"], "기본급")
        self.assertEqual(base["amount"], round(160 * 10320))
        self.assertIn("160h", base["basis"])

    def test_weekly_holiday_amount_matches_hourly_wage_single_source(self):
        result = self._build()
        expected = _hourly.monthly_weekly_holiday_allowance(
            contracted_weekly_hours=40, hourly_rate=10320, perfect_attendance=True
        )
        weekly = next(l for l in result["earnings"] if l["label"] == "주휴수당")
        self.assertEqual(weekly["amount"], expected)
        self.assertIn("40h", weekly["basis"])

    def test_no_weekly_holiday_when_under_15h(self):
        result = self._build(contracted_weekly_hours=10, regular_hours=40)
        labels = [l["label"] for l in result["earnings"]]
        self.assertNotIn("주휴수당", labels)

    def test_no_weekly_holiday_when_not_perfect_attendance(self):
        result = self._build(perfect_attendance=False)
        labels = [l["label"] for l in result["earnings"]]
        self.assertNotIn("주휴수당", labels)

    def test_overtime_night_holiday_leave_all_present(self):
        result = self._build(
            overtime_hours=5, night_hours=3, holiday_work_hours=8, annual_leave_hours=8
        )
        labels = {l["label"] for l in result["earnings"]}
        self.assertTrue({"연장근로수당", "야간근로수당", "휴일근로수당", "연차수당"} <= labels)

    def test_zero_regular_hours_skips_base_line_but_keeps_overtime(self):
        result = self._build(regular_hours=0, contracted_weekly_hours=10, overtime_hours=5)
        labels = [l["label"] for l in result["earnings"]]
        self.assertNotIn("기본급", labels)
        self.assertIn("연장근로수당", labels)

    def test_fractional_hours_formatted_without_trailing_zero(self):
        result = self._build(night_hours=Decimal("4.5"))
        night = next(l for l in result["earnings"] if l["label"] == "야간근로수당")
        self.assertIn("4.5h", night["basis"])
        self.assertNotIn("4.50", night["basis"])


class TestExtraEarningsAndCompliance(unittest.TestCase):
    def test_extra_earning_with_basis_is_included(self):
        result = build_payslip_breakdown(
            employee="박민수",
            period="2026-07",
            payment_date="2026-08-10",
            wage_type="monthly",
            base_salary=2000000,
            extra_earnings=[{"label": "직책수당", "amount": 100000, "basis": "고정 지급(근로계약서 제12조)"}],
        )
        extra = next(l for l in result["earnings"] if l["label"] == "직책수당")
        self.assertEqual(extra["amount"], 100000)
        self.assertEqual(extra["basis"], "고정 지급(근로계약서 제12조)")
        self.assertTrue(result["compliance"]["compliant"])

    def test_extra_earning_without_basis_flagged_noncompliant(self):
        result = build_payslip_breakdown(
            employee="박민수",
            period="2026-07",
            payment_date="2026-08-10",
            wage_type="monthly",
            base_salary=2000000,
            extra_earnings=[{"label": "복리후생비", "amount": 50000}],
        )
        self.assertFalse(result["compliance"]["compliant"])
        self.assertIn("복리후생비", result["compliance"]["missing_basis_labels"])
        # 금액은 그대로 지급합계에 반영되어야 한다 (누락은 표시만, 지급 차단 아님).
        self.assertIn(50000, [l["amount"] for l in result["earnings"]])


class TestValidation(unittest.TestCase):
    def test_missing_employee_raises(self):
        with self.assertRaises(ValueError):
            build_payslip_breakdown(
                employee="", period="2026-07", payment_date="2026-08-10",
                wage_type="monthly", base_salary=2000000,
            )

    def test_invalid_wage_type_raises(self):
        with self.assertRaises(ValueError):
            build_payslip_breakdown(
                employee="김철수", period="2026-07", payment_date="2026-08-10",
                wage_type="weird", base_salary=2000000,
            )

    def test_monthly_missing_base_salary_raises(self):
        with self.assertRaises(ValueError):
            build_payslip_breakdown(
                employee="김철수", period="2026-07", payment_date="2026-08-10",
                wage_type="monthly",
            )

    def test_hourly_missing_contracted_weekly_hours_raises(self):
        with self.assertRaises(ValueError):
            build_payslip_breakdown(
                employee="김철수", period="2026-07", payment_date="2026-08-10",
                wage_type="hourly", hourly_rate=10320,
            )

    def test_negative_base_salary_raises(self):
        with self.assertRaises(ValueError):
            build_payslip_breakdown(
                employee="김철수", period="2026-07", payment_date="2026-08-10",
                wage_type="monthly", base_salary=-1,
            )


class TestRenderMarkdown(unittest.TestCase):
    def test_markdown_includes_legal_required_fields(self):
        result = build_payslip_breakdown(
            employee="김철수",
            period="2026-07",
            payment_date="2026-08-10",
            wage_type="monthly",
            base_salary=2156880,
            overtime_hours=10,
        )
        md = render_payslip_markdown(result)
        self.assertIn("임금명세서", md)
        self.assertIn("2026-08-10", md)
        self.assertIn("기본급", md)
        self.assertIn("계산방법", md)
        self.assertIn("공제내역", md)
        self.assertIn("실지급액", md)
        self.assertIn(f"{result['net_pay']:,}", md)

    def test_markdown_warns_when_noncompliant(self):
        result = build_payslip_breakdown(
            employee="박민수",
            period="2026-07",
            payment_date="2026-08-10",
            wage_type="monthly",
            base_salary=2000000,
            extra_earnings=[{"label": "복리후생비", "amount": 50000}],
        )
        md = render_payslip_markdown(result)
        self.assertIn("§48", md)
        self.assertIn("복리후생비", md)


if __name__ == "__main__":
    unittest.main(verbosity=2)
