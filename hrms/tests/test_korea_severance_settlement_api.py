# -*- coding: utf-8 -*-
"""퇴직정산 통합 API 래퍼 테스트 — framework-free. TDD: RED 먼저.

settle_retirement_api는 코어(severance_settlement.settle_retirement)에 위임하며,
웹 RPC 입력(ISO 날짜 문자열·JSON 문자열 리스트)을 코어 타입으로 변환하고
JSON-safe 결과(Decimal 없음)를 반환해야 한다.

실행: python3 hrms/tests/test_korea_severance_settlement_api.py
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import pathlib
import unittest
from decimal import Decimal

_REPO = pathlib.Path(__file__).resolve().parents[2]
_SK = _REPO / "hrms" / "regional" / "south_korea"


def _load(name):
	path = _SK / (name + ".py")
	spec = importlib.util.spec_from_file_location(name, path)
	m = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(m)
	return m


_api = _load("severance_settlement_api")
_core = _load("severance_settlement")

# PRD 표본: 2020-01-01~2025-01-01(1,827일) 퇴직금이 정확히 50,000,000이 되는 1일 평균임금
_SAMPLE_WAGE = 50_000_000 * 365 / (30 * 1827)


def _assert_no_decimal(obj, path="root"):
	if isinstance(obj, Decimal):
		raise AssertionError(f"Decimal leaked at {path}")
	if isinstance(obj, dict):
		for k, v in obj.items():
			_assert_no_decimal(v, f"{path}.{k}")
	elif isinstance(obj, (list, tuple)):
		for i, v in enumerate(obj):
			_assert_no_decimal(v, f"{path}[{i}]")


class TestSettleRetirementApi(unittest.TestCase):
	def test_prd_sample(self):
		"""표본: 퇴직금 50,000,000 · 2020-01-01~2025-01-01 → 근속 5년 · 소득세 2,143,750 · 지방 214,370."""
		result = _api.settle_retirement_api(
			hire_date="2020-01-01",
			severance_date="2025-01-01",
			average_wage_per_day=_SAMPLE_WAGE,
			monthly_base_salary=2_090_000,
		)
		self.assertEqual(result["payout_summary"]["severance_pay_amount"], 50_000_000)
		self.assertEqual(result["severance_income_tax"]["service_years_rounded"], 5)
		self.assertEqual(result["payout_summary"]["severance_income_tax"], 2_143_750)
		self.assertEqual(result["payout_summary"]["severance_local_income_tax"], 214_370)

	def test_matches_core_full_options(self):
		"""연차수당·건보정산 포함 전체 옵션에서 API 결과가 코어와 일치."""
		kwargs = dict(
			average_wage_per_day=100_000,
			monthly_base_salary=2_090_000,
			ordinary_wage_per_day=110_000,
			unused_leave_days=5,
			monthly_remuneration_for_health=[2_000_000] * 12,
			paid_health_total=71_900 * 11,
			paid_longterm_care_total=0,
			mid_month_hire=False,
		)
		api_result = _api.settle_retirement_api(
			hire_date="2020-01-01", severance_date="2025-01-01", **kwargs
		)
		core_result = _core.settle_retirement(
			hire_date=dt.date(2020, 1, 1), severance_date=dt.date(2025, 1, 1), **kwargs
		)
		self.assertEqual(api_result["payout_summary"], core_result["payout_summary"])
		self.assertEqual(
			api_result["unused_leave_allowance"], core_result["unused_leave_allowance"]
		)
		self.assertEqual(
			api_result["health_insurance_reconciliation"],
			core_result["health_insurance_reconciliation"],
		)
		self.assertEqual(
			api_result["severance_income_tax"]["income_tax"],
			core_result["severance_income_tax"]["income_tax"],
		)

	def test_accepts_json_string_remuneration(self):
		"""Frappe RPC는 리스트를 JSON 문자열로 전달할 수 있다 — 문자열 입력 허용."""
		result = _api.settle_retirement_api(
			hire_date="2020-01-01",
			severance_date="2025-01-01",
			average_wage_per_day=100_000,
			monthly_base_salary=2_090_000,
			monthly_remuneration_for_health=json.dumps([2_000_000] * 6),
		)
		self.assertIsNotNone(result["health_insurance_reconciliation"])
		self.assertEqual(result["health_insurance_reconciliation"]["calc_months"], 6)

	def test_no_health_section_when_not_requested(self):
		result = _api.settle_retirement_api(
			hire_date="2020-01-01",
			severance_date="2025-01-01",
			average_wage_per_day=100_000,
			monthly_base_salary=2_090_000,
		)
		self.assertIsNone(result["health_insurance_reconciliation"])
		self.assertEqual(result["payout_summary"]["health_insurance_settlement"], 0)

	def test_under_one_year_no_tax(self):
		"""1년 미만 재직 → 퇴직금 0 · 퇴직소득세 None."""
		result = _api.settle_retirement_api(
			hire_date="2024-06-01",
			severance_date="2024-09-01",
			average_wage_per_day=100_000,
			monthly_base_salary=2_090_000,
		)
		self.assertFalse(result["severance_pay"]["qualified_for_severance"])
		self.assertIsNone(result["severance_income_tax"])

	def test_json_safe_no_decimal(self):
		"""Frappe RPC 직렬화 안전 — 결과 어디에도 Decimal이 없다."""
		result = _api.settle_retirement_api(
			hire_date="2020-01-01",
			severance_date="2025-01-01",
			average_wage_per_day=100_000,
			monthly_base_salary=2_090_000,
			unused_leave_days=3,
			monthly_remuneration_for_health=[2_000_000] * 12,
		)
		_assert_no_decimal(result)
		json.dumps(result)  # 직렬화 실패 시 예외

	def test_invalid_date_rejected(self):
		with self.assertRaises(ValueError):
			_api.settle_retirement_api(
				hire_date="not-a-date",
				severance_date="2025-01-01",
				average_wage_per_day=100_000,
				monthly_base_salary=2_090_000,
			)


if __name__ == "__main__":
	unittest.main()
