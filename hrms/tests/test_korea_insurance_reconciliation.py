# -*- coding: utf-8 -*-
"""4대보험 고지 대사 코어 테스트 — framework-free.

실사례 회귀: 쿠우쿠우 동탄점 국민연금 4.75% 역산 과다공제(187,730 → 166,500, +21,230)
— 사람 눈이 아니라 이 대사가 잡아야 한다.

실행: python3 hrms/tests/test_korea_insurance_reconciliation.py
"""
from __future__ import annotations

import importlib.util
import pathlib
import unittest

_MODULE_PATH = (
	pathlib.Path(__file__).resolve().parents[1]
	/ "regional"
	/ "south_korea"
	/ "insurance_reconciliation.py"
)
_spec = importlib.util.spec_from_file_location("ins_recon", _MODULE_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

reconcile = _mod.reconcile_contributions
summarize = _mod.summarize_reconciliation_ko


class TestPerfectMatch(unittest.TestCase):
	def test_all_match(self):
		rows = [
			{"employee": "E1", "national_pension": 166500, "health_insurance": 131160},
			{"employee": "E2", "national_pension": 90000, "health_insurance": 70900},
		]
		out = reconcile(rows, [dict(r) for r in rows])
		self.assertTrue(out["ok"])
		self.assertEqual(out["match_count"], 4)
		self.assertEqual(out["diffs"], [])
		self.assertIn("전부 1원 단위 일치", summarize(out))


class TestKuukuuRegressionCase(unittest.TestCase):
	"""쿠우쿠우 4.75% 과다공제 실사례 — 우리 공제 187,730 vs 정상(고지) 166,500."""

	def test_overdeduction_detected(self):
		computed = [{"employee": "천시원", "national_pension": 187730}]
		notified = [{"employee": "천시원", "national_pension": 166500}]
		out = reconcile(computed, notified)
		self.assertFalse(out["ok"])
		self.assertEqual(len(out["diffs"]), 1)
		d = out["diffs"][0]
		self.assertEqual(d["label"], "국민연금")
		self.assertEqual(d["delta"], 21230)  # 양수 = 과다공제 의심
		self.assertIn("과다 1", summarize(out))
		self.assertIn("+21,230", summarize(out))

	def test_one_won_matters(self):
		# 1원 차이도 diff (tolerance 기본 0 — 글로벌 1원 단위 규칙)
		out = reconcile(
			[{"employee": "E1", "national_pension": 100001}],
			[{"employee": "E1", "national_pension": 100000}],
		)
		self.assertEqual(len(out["diffs"]), 1)

	def test_tolerance_explicit(self):
		out = reconcile(
			[{"employee": "E1", "national_pension": 100010}],
			[{"employee": "E1", "national_pension": 100000}],
			tolerance=10,
		)
		self.assertTrue(out["ok"])


class TestMissingAndPartial(unittest.TestCase):
	def test_missing_both_directions(self):
		out = reconcile(
			[{"employee": "E1", "national_pension": 100}, {"employee": "E2", "national_pension": 100}],
			[{"employee": "E2", "national_pension": 100}, {"employee": "E3", "national_pension": 100}],
		)
		self.assertEqual(out["missing_in_notified"], ["E1"])
		self.assertEqual(out["missing_in_computed"], ["E3"])
		self.assertFalse(out["ok"])
		self.assertIn("고지 누락 1명", summarize(out))

	def test_partial_fields_only_compared(self):
		# 고지에 고용보험만 있으면 그 필드만 대조 (없는 필드는 diff 아님)
		out = reconcile(
			[{"employee": "E1", "national_pension": 100, "employment_insurance": 50}],
			[{"employee": "E1", "employment_insurance": 50}],
		)
		self.assertTrue(out["ok"])
		self.assertEqual(out["match_count"], 1)

	def test_totals(self):
		out = reconcile(
			[{"employee": "E1", "national_pension": 100}, {"employee": "E2", "national_pension": 200}],
			[{"employee": "E1", "national_pension": 90}, {"employee": "E2", "national_pension": 200}],
		)
		np_tot = out["totals"]["national_pension"]
		self.assertEqual(np_tot, {"computed": 300, "notified": 290, "delta": 10})


class TestValidation(unittest.TestCase):
	def test_duplicate_key_rejected(self):
		with self.assertRaises(ValueError):
			reconcile(
				[{"employee": "E1", "national_pension": 1}, {"employee": "E1", "national_pension": 2}],
				[],
			)

	def test_missing_key_rejected(self):
		with self.assertRaises(ValueError):
			reconcile([{"national_pension": 1}], [])

	def test_non_integer_amount_rejected(self):
		with self.assertRaises(ValueError):
			reconcile(
				[{"employee": "E1", "national_pension": 100.5}],
				[{"employee": "E1", "national_pension": 100}],
			)

	def test_negative_tolerance_rejected(self):
		with self.assertRaises(ValueError):
			reconcile([], [], tolerance=-1)

	def test_diffs_sorted_by_magnitude(self):
		out = reconcile(
			[
				{"employee": "A", "national_pension": 105},
				{"employee": "B", "national_pension": 200},
			],
			[
				{"employee": "A", "national_pension": 100},
				{"employee": "B", "national_pension": 100},
			],
		)
		self.assertEqual([d["employee"] for d in out["diffs"]], ["B", "A"])  # |100| > |5|


class TestContributionRowsFromSlips(unittest.TestCase):
	def test_basic_mapping_and_sum(self):
		slips = [{
			"employee": "E1",
			"deductions": [
				{"salary_component": "국민연금", "amount": 166500},
				{"salary_component": "건강보험", "amount": 131160},
				{"salary_component": "장기요양보험", "amount": 16980},
				{"salary_component": "고용보험", "amount": 33300},
				{"salary_component": "소득세", "amount": 84850},          # 4대 아님 → unmapped
				{"salary_component": "국민연금 정산", "amount": 1000},     # 같은 보험 합산
			],
		}]
		out = _mod.contribution_rows_from_slips(slips)
		row = out["rows"][0]
		self.assertEqual(row["national_pension"], 167500)   # 166500 + 1000
		self.assertEqual(row["health_insurance"], 131160)
		self.assertEqual(row["long_term_care_insurance"], 16980)  # "장기요양"이 "건강보험"보다 먼저 매칭
		self.assertEqual(row["employment_insurance"], 33300)
		self.assertEqual(out["unmapped"], [{"employee": "E1", "component": "소득세", "amount": 84850}])

	def test_label_fallback_and_float_rounding(self):
		slips = [{"employee": "E2", "deductions": [{"label": "건강보험료", "amount": 100.4}]}]
		out = _mod.contribution_rows_from_slips(slips)
		self.assertEqual(out["rows"][0]["health_insurance"], 100)

	def test_slips_to_reconcile_end_to_end(self):
		slips = [{"employee": "천시원", "deductions": [{"salary_component": "국민연금", "amount": 187730}]}]
		computed = _mod.contribution_rows_from_slips(slips)["rows"]
		notified = [{"employee": "천시원", "national_pension": 166500}]
		out = reconcile(computed, notified)
		self.assertEqual(out["diffs"][0]["delta"], 21230)


if __name__ == "__main__":
	unittest.main()
