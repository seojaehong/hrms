# -*- coding: utf-8 -*-
"""임금명세서 분해 API 래퍼 테스트 — framework-free. TDD: RED 먼저.

payslip_breakdown_api는 코어(payslip_breakdown)에 위임하며, 월급제/시급제 각
표본이 코어와 일치하고 missing_basis_labels가 그대로 전달되는지 검증한다.

실행: python3 hrms/tests/test_korea_payslip_breakdown_api.py
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import unittest

_REPO = pathlib.Path(__file__).resolve().parents[2]
_SK = _REPO / "hrms" / "regional" / "south_korea"


def _load(name):
	path = _SK / (name + ".py")
	spec = importlib.util.spec_from_file_location(name, path)
	m = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(m)
	return m


_api = _load("payslip_breakdown_api")
_core = _load("payslip_breakdown")


class TestBuildPayslipBreakdownApiMonthly(unittest.TestCase):
	def _params(self, **overrides):
		params = dict(
			employee="김철수",
			period="2026-07",
			payment_date="2026-08-10",
			wage_type="monthly",
			base_salary=2156880,
		)
		params.update(overrides)
		return params

	def test_matches_core(self):
		params = self._params(overtime_hours=10)
		api_result = _api.build_payslip_breakdown_api(**params)
		core_result = _core.build_payslip_breakdown(**params)
		self.assertEqual(api_result, core_result)

	def test_base_salary_line(self):
		result = _api.build_payslip_breakdown_api(**self._params())
		base = result["earnings"][0]
		self.assertEqual(base["label"], "기본급")
		self.assertEqual(base["amount"], 2156880)
		self.assertIn("209h", base["basis"])

	def test_json_safe(self):
		result = _api.build_payslip_breakdown_api(**self._params())
		json.dumps(result)


class TestBuildPayslipBreakdownApiHourly(unittest.TestCase):
	def _params(self, **overrides):
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
		return params

	def test_matches_core(self):
		params = self._params(overtime_hours=5, night_hours=3)
		api_result = _api.build_payslip_breakdown_api(**params)
		core_result = _core.build_payslip_breakdown(**params)
		self.assertEqual(api_result, core_result)

	def test_weekly_holiday_line_present(self):
		result = _api.build_payslip_breakdown_api(**self._params())
		labels = [l["label"] for l in result["earnings"]]
		self.assertIn("주휴수당", labels)

	def test_json_safe(self):
		result = _api.build_payslip_breakdown_api(**self._params())
		json.dumps(result)


class TestBuildPayslipBreakdownApiMissingBasis(unittest.TestCase):
	def test_missing_basis_labels_passed_through(self):
		"""extra_earnings가 JSON 문자열 리스트여도(Frappe RPC 관례) basis 누락이 전달된다."""
		params = dict(
			employee="박민수",
			period="2026-07",
			payment_date="2026-08-10",
			wage_type="monthly",
			base_salary=2000000,
			extra_earnings=json.dumps([{"label": "복리후생비", "amount": 50000}]),
		)
		result = _api.build_payslip_breakdown_api(**params)
		self.assertFalse(result["compliance"]["compliant"])
		self.assertIn("복리후생비", result["compliance"]["missing_basis_labels"])

	def test_invalid_wage_type_rejected(self):
		with self.assertRaises(ValueError):
			_api.build_payslip_breakdown_api(
				employee="김철수",
				period="2026-07",
				payment_date="2026-08-10",
				wage_type="annual",
				base_salary=2000000,
			)


class TestRenderPayslipMarkdownApi(unittest.TestCase):
	def test_matches_core(self):
		params = dict(
			employee="김철수",
			period="2026-07",
			payment_date="2026-08-10",
			wage_type="monthly",
			base_salary=2156880,
		)
		breakdown = _core.build_payslip_breakdown(**params)
		api_md = _api.render_payslip_markdown_api(breakdown)
		core_md = _core.render_payslip_markdown(breakdown)
		self.assertEqual(api_md, core_md)
		self.assertIn("김철수", api_md)

	def test_accepts_json_string_breakdown(self):
		"""Frappe RPC가 dict를 JSON 문자열로 전달하는 경우도 허용."""
		params = dict(
			employee="김철수",
			period="2026-07",
			payment_date="2026-08-10",
			wage_type="monthly",
			base_salary=2156880,
		)
		breakdown = _core.build_payslip_breakdown(**params)
		api_md = _api.render_payslip_markdown_api(json.dumps(breakdown))
		core_md = _core.render_payslip_markdown(breakdown)
		self.assertEqual(api_md, core_md)


if __name__ == "__main__":
	unittest.main()
