#!/usr/bin/env python3
"""PWA 임금명세서 어댑터 테스트 — wage_statement.py 신규 엔드포인트.

검증 범위:
  - map_salary_slip_to_wage_statement: 노호 류두선(HR-EMP-00004) 5월 실측 슬립으로
    1원 단위 합계 크로스체크 (gross 8,333,333 / 공제 1,851,780 / net 6,481,553)
  - build_wage_statement_history: date/str start_date → pay_year_month 변환
  - list_korea_wage_statements / build_korea_wage_statement_preview:
    FakeFrappe 주입으로 권한(본인/HR Manager)·조회 필터·throw 경로 검증

framework-free: python3 로 직접 실행 (frappe 미설치 환경).
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import types
import unittest
from datetime import date

_SOUTH_KOREA = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea"
WS_MODULE_PATH = _SOUTH_KOREA / "wage_statement.py"


# ---------------------------------------------------------------------------
# FakeFrappe (test_korea_admin_dashboard_runtime_api.py 컨벤션)
# ---------------------------------------------------------------------------


class FakeThrow(Exception):
    pass


class FakeDB:
    def __init__(self, employee_by_user=None):
        self.employee_by_user = dict(employee_by_user or {})
        self.get_value_calls = []

    def get_value(self, doctype, filters, fieldname):
        self.get_value_calls.append({"doctype": doctype, "filters": filters, "fieldname": fieldname})
        if doctype == "Employee" and isinstance(filters, dict):
            return self.employee_by_user.get(filters.get("user_id"))
        return None


class FakeFrappe(types.ModuleType):
    def __init__(self, *, user="ryu@noho.kr", roles=None, employee_by_user=None, slips=None, docs=None):
        super().__init__("frappe")
        self.session = types.SimpleNamespace(user=user)
        self.roles = list(roles or [])
        self.db = FakeDB(employee_by_user)
        self.slips = list(slips or [])
        self.docs = dict(docs or {})
        self.get_all_calls = []
        self.whitelisted = []

    def whitelist(self, *args, **kwargs):
        def decorator(fn):
            self.whitelisted.append(fn.__name__)
            return fn

        return decorator

    def get_roles(self, user=None):
        return list(self.roles)

    def get_all(self, doctype, filters=None, fields=None, order_by=None, limit=None):
        self.get_all_calls.append(
            {"doctype": doctype, "filters": filters, "fields": fields, "order_by": order_by, "limit": limit}
        )
        return list(self.slips)

    def get_doc(self, doctype, name):
        return self.docs[(doctype, name)]

    def throw(self, message, *args, **kwargs):
        raise FakeThrow(message)


def load_module(fake_frappe=None):
    old_frappe = sys.modules.get("frappe")
    if fake_frappe is not None:
        sys.modules["frappe"] = fake_frappe
    else:
        sys.modules.pop("frappe", None)
    try:
        spec = importlib.util.spec_from_file_location("korea_wage_statement_adapter", WS_MODULE_PATH)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module
    finally:
        if old_frappe is not None:
            sys.modules["frappe"] = old_frappe
        else:
            sys.modules.pop("frappe", None)


# ---------------------------------------------------------------------------
# 실측 데이터 — 노호 류두선(HR-EMP-00004) 2026년 5월 Salary Slip
# ---------------------------------------------------------------------------

RYU_MAY_SLIP = {
    "earnings": [
        {"salary_component": "기본급", "amount": 6_908_843},
        {"salary_component": "고정연장수당", "amount": 1_224_490},
        {"salary_component": "식대(비과세)", "amount": 200_000},
    ],
    "deductions": [
        {"salary_component": "소득세", "amount": 1_032_080},
        {"salary_component": "지방소득세", "amount": 103_200},
        {"salary_component": "국민연금", "amount": 302_570},
        {"salary_component": "건강보험", "amount": 299_580},
        {"salary_component": "장기요양보험", "amount": 39_360},
        {"salary_component": "고용보험", "amount": 74_990},
    ],
    "total_deduction": 1_851_780,
    "net_pay": 6_481_553,
}

RYU_GROSS = 8_333_333
RYU_TOTAL_DEDUCTION = 1_851_780
RYU_NET = 6_481_553


class TestMapSalarySlipToWageStatement(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()

    def test_ryu_may_real_slip_maps_exactly(self):
        stmt = self.mod.map_salary_slip_to_wage_statement(RYU_MAY_SLIP)

        self.assertEqual(stmt["base_salary"], 6_908_843)
        self.assertEqual(
            stmt["allowances"],
            [{"code": "고정연장수당", "label": "고정연장수당", "amount": 1_224_490}],
        )
        self.assertEqual(stmt["non_taxable_total"], 200_000)
        self.assertEqual(stmt["income_tax"], 1_032_080)
        self.assertEqual(stmt["local_income_tax"], 103_200)
        self.assertEqual(stmt["national_pension"], 302_570)
        self.assertEqual(stmt["health_insurance"], 299_580)
        self.assertEqual(stmt["long_term_care_insurance"], 39_360)
        self.assertEqual(stmt["employment_insurance"], 74_990)
        self.assertEqual(stmt["total_deduction"], RYU_TOTAL_DEDUCTION)
        self.assertEqual(stmt["net_pay"], RYU_NET)

    def test_ryu_may_sums_cross_check_to_the_won(self):
        """1원 단위 합계 검증 — base + allowances + non_taxable == gross,
        공제 6종 합 == total_deduction, gross - total_deduction == net."""
        stmt = self.mod.map_salary_slip_to_wage_statement(RYU_MAY_SLIP)

        allowance_total = sum(item["amount"] for item in stmt["allowances"])
        self.assertEqual(stmt["base_salary"] + allowance_total + stmt["non_taxable_total"], RYU_GROSS)

        deduction_total = (
            stmt["income_tax"]
            + stmt["local_income_tax"]
            + stmt["national_pension"]
            + stmt["health_insurance"]
            + stmt["long_term_care_insurance"]
            + stmt["employment_insurance"]
        )
        self.assertEqual(deduction_total, RYU_TOTAL_DEDUCTION)
        self.assertEqual(RYU_GROSS - stmt["total_deduction"], stmt["net_pay"])

    def test_base_salary_falls_back_to_first_earning(self):
        slip = {
            "earnings": [
                {"salary_component": "월급여", "amount": 2_000_000},
                {"salary_component": "직책수당", "amount": 100_000},
            ],
            "deductions": [],
            "total_deduction": 0,
            "net_pay": 2_100_000,
        }
        stmt = self.mod.map_salary_slip_to_wage_statement(slip)
        self.assertEqual(stmt["base_salary"], 2_000_000)
        self.assertEqual(stmt["allowances"], [{"code": "직책수당", "label": "직책수당", "amount": 100_000}])
        self.assertEqual(stmt["non_taxable_total"], 0)

    def test_local_income_tax_not_double_counted_as_income_tax(self):
        """'지방소득세'는 '소득세'를 부분 문자열로 포함 — income_tax 에 섞이면 안 됨."""
        slip = {
            "earnings": [{"salary_component": "기본급", "amount": 1_000_000}],
            "deductions": [{"salary_component": "지방소득세", "amount": 5_000}],
            "total_deduction": 5_000,
            "net_pay": 995_000,
        }
        stmt = self.mod.map_salary_slip_to_wage_statement(slip)
        self.assertEqual(stmt["income_tax"], 0)
        self.assertEqual(stmt["local_income_tax"], 5_000)

    def test_long_term_care_not_counted_as_health_insurance(self):
        slip = {
            "earnings": [{"salary_component": "기본급", "amount": 1_000_000}],
            "deductions": [{"salary_component": "건강보험(장기요양)", "amount": 12_000}],
            "total_deduction": 12_000,
            "net_pay": 988_000,
        }
        stmt = self.mod.map_salary_slip_to_wage_statement(slip)
        self.assertEqual(stmt["long_term_care_insurance"], 12_000)
        self.assertEqual(stmt["health_insurance"], 0)

    def test_float_amounts_forced_to_integer_krw(self):
        slip = {
            "earnings": [{"salary_component": "기본급", "amount": 1_000_000.0}],
            "deductions": [{"salary_component": "소득세", "amount": 12_345.0}],
            "total_deduction": 12_345.0,
            "net_pay": 987_655.0,
        }
        stmt = self.mod.map_salary_slip_to_wage_statement(slip)
        self.assertIsInstance(stmt["base_salary"], int)
        self.assertIsInstance(stmt["income_tax"], int)
        self.assertIsInstance(stmt["net_pay"], int)
        self.assertEqual(stmt["net_pay"], 987_655)


class TestBuildWageStatementHistory(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()

    def test_date_and_string_start_dates(self):
        rows = [
            {"start_date": date(2026, 5, 1), "net_pay": 6_481_553},
            {"start_date": "2026-04-01", "net_pay": 6_481_553.0},
        ]
        history = self.mod.build_wage_statement_history(rows)
        self.assertEqual(
            history,
            [
                {"pay_year_month": "2026-05", "net_pay": 6_481_553},
                {"pay_year_month": "2026-04", "net_pay": 6_481_553},
            ],
        )

    def test_rows_without_start_date_are_skipped(self):
        history = self.mod.build_wage_statement_history([{"net_pay": 100}, {"start_date": None, "net_pay": 1}])
        self.assertEqual(history, [])


class TestListKoreaWageStatements(unittest.TestCase):
    def _fake(self, **kwargs):
        defaults = dict(
            user="ryu@noho.kr",
            roles=["Employee"],
            employee_by_user={"ryu@noho.kr": "HR-EMP-00004"},
            slips=[
                {"start_date": date(2026, 5, 1), "net_pay": 6_481_553},
                {"start_date": date(2026, 4, 1), "net_pay": 6_400_000},
            ],
        )
        defaults.update(kwargs)
        return FakeFrappe(**defaults)

    def test_own_employee_gets_history_with_expected_filters(self):
        fake = self._fake()
        mod = load_module(fake)
        result = mod.list_korea_wage_statements("HR-EMP-00004", limit="12")
        self.assertEqual(
            result,
            [
                {"pay_year_month": "2026-05", "net_pay": 6_481_553},
                {"pay_year_month": "2026-04", "net_pay": 6_400_000},
            ],
        )
        call = fake.get_all_calls[0]
        self.assertEqual(call["doctype"], "Salary Slip")
        self.assertEqual(call["filters"], {"employee": "HR-EMP-00004", "docstatus": ["in", [0, 1]]})
        self.assertEqual(call["order_by"], "start_date desc")
        self.assertEqual(call["limit"], 12)
        self.assertIn("list_korea_wage_statements", fake.whitelisted)

    def test_other_employee_denied_without_hr_manager(self):
        fake = self._fake()
        mod = load_module(fake)
        with self.assertRaises(PermissionError):
            mod.list_korea_wage_statements("HR-EMP-00099")
        self.assertEqual(fake.get_all_calls, [])

    def test_hr_manager_can_read_other_employee(self):
        fake = self._fake(user="hr@noho.kr", roles=["HR Manager"], employee_by_user={})
        mod = load_module(fake)
        result = mod.list_korea_wage_statements("HR-EMP-00004")
        self.assertEqual(len(result), 2)

    def test_invalid_employee_or_limit_rejected_before_query(self):
        fake = self._fake()
        mod = load_module(fake)
        with self.assertRaises(ValueError):
            mod.list_korea_wage_statements("  ")
        with self.assertRaises(ValueError):
            mod.list_korea_wage_statements("HR-EMP-00004", limit="abc")
        self.assertEqual(fake.get_all_calls, [])


class TestBuildKoreaWageStatementPreview(unittest.TestCase):
    def _fake_with_doc(self):
        doc = dict(RYU_MAY_SLIP)  # dict 자식행도 _row_value 접근자로 지원
        return FakeFrappe(
            user="ryu@noho.kr",
            roles=["Employee"],
            employee_by_user={"ryu@noho.kr": "HR-EMP-00004"},
            slips=[{"name": "Sal Slip/HR-EMP-00004/00005"}],
            docs={("Salary Slip", "Sal Slip/HR-EMP-00004/00005"): doc},
        )

    def test_preview_returns_mapped_statement_for_month(self):
        fake = self._fake_with_doc()
        mod = load_module(fake)
        stmt = mod.build_korea_wage_statement_preview("HR-EMP-00004", "2026", "5")
        self.assertEqual(stmt["base_salary"], 6_908_843)
        self.assertEqual(stmt["net_pay"], RYU_NET)
        call = fake.get_all_calls[0]
        self.assertEqual(
            call["filters"],
            {
                "employee": "HR-EMP-00004",
                "docstatus": ["in", [0, 1]],
                "start_date": ["between", ["2026-05-01", "2026-05-31"]],
            },
        )
        self.assertIn("build_korea_wage_statement_preview", fake.whitelisted)

    def test_missing_month_throws_korean_message(self):
        fake = self._fake_with_doc()
        fake.slips = []
        mod = load_module(fake)
        with self.assertRaisesRegex(FakeThrow, "해당 월의 명세서가 없습니다"):
            mod.build_korea_wage_statement_preview("HR-EMP-00004", 2026, 6)

    def test_other_employee_denied(self):
        fake = self._fake_with_doc()
        mod = load_module(fake)
        with self.assertRaises(PermissionError):
            mod.build_korea_wage_statement_preview("HR-EMP-00099", 2026, 5)
        self.assertEqual(fake.get_all_calls, [])

    def test_invalid_month_rejected(self):
        fake = self._fake_with_doc()
        mod = load_module(fake)
        with self.assertRaises(ValueError):
            mod.build_korea_wage_statement_preview("HR-EMP-00004", 2026, 13)


if __name__ == "__main__":
    unittest.main()
