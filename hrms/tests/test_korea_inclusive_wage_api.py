# -*- coding: utf-8 -*-
"""포괄임금 설계·역산 API 래퍼 — framework-free. TDD: RED 먼저.

API는 최저시급을 인자로 받지 않고 서버에서 published 온톨로지
(wiki/ontology/법정수치/최저임금_<연도>.md)로 조회해 코어에 주입한다.
코어(inclusive_wage.py)와 동일 결과를 보장하는 위임 계약을 검증한다.

실행: python3 hrms/tests/test_korea_inclusive_wage_api.py
"""
from __future__ import annotations

import datetime
import importlib.util
import pathlib
import unittest

_REPO = pathlib.Path(__file__).resolve().parents[2]
_SK = _REPO / "hrms" / "regional" / "south_korea"


def _load(name, sub=""):
	path = _SK / (sub + name + ".py") if sub else _SK / (name + ".py")
	spec = importlib.util.spec_from_file_location(name, path)
	m = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(m)
	return m


_api = _load("inclusive_wage_api")
_core = _load("inclusive_wage")
_stat = _load("statutory_ontology", "ontology/")

_WIKI = _REPO / "wiki" / "ontology"
_YEAR = datetime.date.today().year
_MIN_WAGE = _stat.get_minimum_hourly_wage(_WIKI, _YEAR)


class TestDesignApi(unittest.TestCase):
	def test_sample_matches_prd(self):
		"""표본: 총액 3,000,000 / OT 20h → 기본급 2,623,431 · 연장 376,569."""
		result = _api.design_inclusive_wage_api(3_000_000, 20)
		self.assertEqual(result["base_pay"], 2_623_431)
		self.assertEqual(result["fixed_ot_pay"], 376_569)
		self.assertEqual(result["total"], 3_000_000)

	def test_matches_core_with_injected_minimum_wage(self):
		"""API 결과가 코어(최저시급 주입) 결과와 항목별 일치."""
		api_result = _api.design_inclusive_wage_api(
			3_000_000, 20, fixed_night_hours=10, fixed_holiday_hours=8
		)
		core_result = _core.design_inclusive_wage(
			3_000_000, 20, 10, 8, minimum_hourly_wage=_MIN_WAGE
		)
		for key in ("base_pay", "fixed_ot_pay", "night_pay", "holiday_pay", "total",
		            "legal_floor_ok", "warnings"):
			self.assertEqual(api_result[key], core_result[key], key)
		self.assertAlmostEqual(
			float(api_result["ordinary_hourly_wage"]),
			float(core_result["ordinary_hourly_wage"]),
			places=4,
		)

	def test_minimum_wage_auto_injected(self):
		"""최저시급은 인자가 아니라 서버가 온톨로지에서 주입 — 결과에 노출."""
		self.assertIsNotNone(_MIN_WAGE, "온톨로지에 올해 최저임금 published 노드 필요")
		result = _api.design_inclusive_wage_api(3_000_000, 20)
		self.assertEqual(result["minimum_hourly_wage"], _MIN_WAGE)

	def test_json_safe_types(self):
		"""Frappe RPC 직렬화 안전 — Decimal이 결과에 남지 않는다."""
		result = _api.design_inclusive_wage_api(3_000_000, 20)
		self.assertIsInstance(result["ordinary_hourly_wage"], float)

	def test_low_total_warns_minimum_wage(self):
		"""통상시급이 최저임금 미만이면 warnings에 최저임금법 §6 경고."""
		result = _api.design_inclusive_wage_api(1_000_000, 0)
		self.assertFalse(result["legal_floor_ok"])
		self.assertTrue(any("최저임금" in w for w in result["warnings"]))


class TestAuditApi(unittest.TestCase):
	def test_matches_core_with_injected_minimum_wage(self):
		api_result = _api.audit_inclusive_wage_api(
			base_pay=2_623_431,
			fixed_ot_pay=300_000,
			fixed_ot_hours=20,
			fixed_night_pay=0,
			fixed_night_hours=0,
			fixed_holiday_pay=0,
			fixed_holiday_hours=0,
		)
		core_result = _core.audit_inclusive_wage(
			base_pay=2_623_431,
			fixed_ot_pay=300_000,
			fixed_ot_hours=20,
			minimum_hourly_wage=_MIN_WAGE,
		)
		for key in ("expected_ot_pay", "expected_night_pay", "expected_holiday_pay",
		            "ot_shortfall", "night_shortfall", "holiday_shortfall",
		            "legal_floor_ok", "overtime_limit_ok", "warnings"):
			self.assertEqual(api_result[key], core_result[key], key)
		self.assertAlmostEqual(
			float(api_result["ordinary_hourly_wage"]),
			float(core_result["ordinary_hourly_wage"]),
			places=4,
		)
		self.assertEqual(api_result["minimum_hourly_wage"], _MIN_WAGE)

	def test_shortfall_detected(self):
		"""연장수당 기재액이 적정액보다 적으면 부족분 검출."""
		result = _api.audit_inclusive_wage_api(
			base_pay=2_623_431, fixed_ot_pay=300_000, fixed_ot_hours=20
		)
		self.assertGreater(result["ot_shortfall"], 0)
		self.assertIsInstance(result["ordinary_hourly_wage"], float)


if __name__ == "__main__":
	unittest.main()
