# -*- coding: utf-8 -*-
"""MCP 서버 신규 계산 도구(시급제·고지대사) 테스트 — framework-free. TDD: RED 먼저.

server.py는 mcp SDK를 import하므로 패키지 전체 로드 불가 → 도구 함수를 순수 로직
모듈(mcp_server/calc_tools.py)로 분리해 직접 테스트한다(FastMCP는 그 함수를 등록만).

실행: python3 hrms/tests/test_korea_mcp_hourly_recon_tools.py
"""
from __future__ import annotations

import importlib.util
import pathlib
import unittest

_MODULE_PATH = pathlib.Path(__file__).resolve().parents[2] / "mcp_server" / "calc_tools.py"
_spec = importlib.util.spec_from_file_location("calc_tools", _MODULE_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

estimate_hourly = _mod.estimate_hourly_pay
reconcile = _mod.check_insurance_reconciliation


class TestEstimateHourlyPay(unittest.TestCase):
	def test_monthly_buckets(self):
		# 정상 80h + 주휴(주20h) · 시급 10,030
		out = estimate_hourly(regular_hours=80, hourly_rate=10030, contracted_weekly_hours=20)
		comp = {e["component"]: e["amount"] for e in out["earnings"]}
		self.assertEqual(comp["기본급"], 802400)  # 80 × 10030
		self.assertIn("주휴수당", comp)
		self.assertEqual(out["gross_pay"], sum(comp.values()))
		self.assertIn("below_minimum_wage", out)

	def test_overtime_and_min_wage_flag(self):
		out = estimate_hourly(regular_hours=160, overtime_hours=10, hourly_rate=9000,
			contracted_weekly_hours=40, minimum_wage=10030)
		comp = {e["component"]: e["amount"] for e in out["earnings"]}
		self.assertEqual(comp["연장근로수당"], 135000)  # 10 × 9000 × 1.5
		self.assertTrue(out["below_minimum_wage"])

	def test_zero_rate_rejected(self):
		with self.assertRaises(ValueError):
			estimate_hourly(regular_hours=10, hourly_rate=0, contracted_weekly_hours=20)


class TestReconciliation(unittest.TestCase):
	def test_kuukuu_overdeduction(self):
		out = reconcile(
			computed=[{"employee": "천시원", "national_pension": 187730}],
			notified=[{"employee": "천시원", "national_pension": 166500}],
		)
		self.assertFalse(out["ok"])
		self.assertEqual(out["diffs"][0]["delta"], 21230)
		self.assertIn("summary_ko", out)
		self.assertIn("+21,230", out["summary_ko"])

	def test_match(self):
		rows = [{"employee": "E1", "national_pension": 90000}]
		out = reconcile(computed=rows, notified=[dict(r) for r in rows])
		self.assertTrue(out["ok"])


class TestMinimumWageFromOntology(unittest.TestCase):
	"""사고 방지: minimum_wage 미지정 시 온톨로지 published 확정값(2026=10,320)으로 판정."""

	def test_10030_flagged_violation_via_ontology_default(self):
		# 시급 10,030 · 최저임금 인자 없음 → 온톨로지 2026값 10,320 기준 위반 판정
		out = estimate_hourly(regular_hours=80, hourly_rate=10030, contracted_weekly_hours=20)
		self.assertTrue(out["below_minimum_wage"])
		self.assertEqual(out.get("minimum_wage_applied"), 10320)

	def test_explicit_minimum_wage_overrides(self):
		out = estimate_hourly(regular_hours=80, hourly_rate=10030, contracted_weekly_hours=20, minimum_wage=9000)
		self.assertFalse(out["below_minimum_wage"])
		self.assertEqual(out.get("minimum_wage_applied"), 9000)


if __name__ == "__main__":
	unittest.main()
