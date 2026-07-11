# -*- coding: utf-8 -*-
"""4대보험 요율 단일소스 가드 — 모듈별 하드코딩이 statutory_2026과 어긋나는 사고 방지.

배경: 2026-07 검수에서 foreign_worker(2024 요율)·leave_of_absence(2025 요율) 잔존 발견.
상봉 6월 신구 요율 혼재 사고(검증18)의 코드측 근본 대책. TDD: RED 먼저.
"""
import importlib.util
import pathlib
import unittest

_SK = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, _SK / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


_stat = _load("statutory_2026")
_foreign = _load("foreign_worker")
_loa = _load("leave_of_absence")


class ForeignWorkerRates(unittest.TestCase):
    def test_rates_match_statutory_2026(self):
        rates = _foreign.get_insurance_rates()
        self.assertAlmostEqual(rates["national_pension_employee_rate"], _stat.PENSION_RATE_EMPLOYEE)
        self.assertAlmostEqual(rates["national_pension_employer_rate"], _stat.PENSION_RATE_EMPLOYER)
        self.assertAlmostEqual(rates["health_insurance_employee_rate"], _stat.HEALTH_RATE_EMPLOYEE)
        self.assertAlmostEqual(rates["health_insurance_employer_rate"], _stat.HEALTH_RATE_EMPLOYER)
        self.assertAlmostEqual(rates["long_term_care_rate_on_health"], _stat.LONGTERM_CARE_RATE)
        self.assertAlmostEqual(rates["employment_insurance_employee_rate"], _stat.EMPLOYMENT_INSURANCE_RATE_EMPLOYEE)


class LeaveOfAbsenceRates(unittest.TestCase):
    def test_rates_match_statutory_2026(self):
        self.assertAlmostEqual(_loa.PENSION_EMPLOYER_RATE, _stat.PENSION_RATE_EMPLOYER)
        self.assertAlmostEqual(_loa.PENSION_EMPLOYEE_RATE, _stat.PENSION_RATE_EMPLOYEE)
        self.assertAlmostEqual(_loa.HEALTH_INSURANCE_EMPLOYER_RATE, _stat.HEALTH_RATE_EMPLOYER)


if __name__ == "__main__":
    unittest.main()
