# -*- coding: utf-8 -*-
"""Direct-run tests for Korea work rules (취업규칙) judgment helpers.

framework-free: spec_from_file_location 직접 로드, frappe 불필요.
근거: 근로기준법 §93(필수기재·신고의무) §94(작성·변경 절차, 불이익변경 동의)
      §95(제재 규정 제한) §14(게시). 조문은 korean-law MCP(get_law_text,
      mst=265959)로 2026-07-11 확인한 현행(시행 2025-10-23)본 기준.
불이익변경 해당 여부는 이 모듈이 단정하지 않는다 — candidate 판정 + 노무사 확인
플래그만 반환한다(개인 스킬 취업규칙검토의 보수적 원칙 준수).
"""

from __future__ import annotations

import importlib.util
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "work_rules.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_work_rules", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


class TestRequiredItemsChecklist(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()

	def test_fourteen_required_items_defined(self):
		# 근기법 §93 각 호(9의2 포함) = 14개 항목.
		self.assertEqual(len(self.mod.WORK_RULES_REQUIRED_ITEMS), 14)
		hos = [item["ho"] for item in self.mod.WORK_RULES_REQUIRED_ITEMS]
		self.assertIn("9의2", hos)
		self.assertIn("11", hos)
		self.assertEqual(len(hos), len(set(hos)))

	def test_check_required_items_dict_input_all_covered(self):
		rules_outline = {
			"1": "업무의 시작과 종료 시각은 09:00부터 18:00, 휴게시간은 12시부터 13시, 휴일은 주휴일, 연차휴가, 교대근로 규정",
			"2": "임금은 매월 25일 지급하며 산정기간은 전월 1일부터 말일까지, 계산방법은 별도 규정, 승급은 매년 1회",
			"3": "가족수당은 지급하지 아니한다",
			"4": "근로자는 정년 도달 시 퇴직한다",
			"5": "퇴직급여제도는 퇴직금제로 하며 상여금 및 최저임금은 관계법령에 따른다",
			"6": "식비는 회사가 전액 부담하고 작업용품은 회사가 지급한다",
			"7": "교육시설은 별도로 두지 아니한다",
			"8": "출산전후휴가 및 육아휴직 등 모성보호와 일가정 양립을 지원한다",
			"9": "안전과 보건에 관하여는 산업안전보건법에 따른다",
			"9의2": "성별 연령 신체적 조건 등 특성에 따라 사업장 환경을 개선한다",
			"10": "업무상 및 업무 외 재해부조에 관한 사항은 관계법령에 따른다",
			"11": "직장 내 괴롭힘 예방 교육을 실시하고 발생 시 조사 등 조치를 취한다",
			"12": "표창 및 제재에 관한 사항은 별도 규정에 따른다",
			"13": "그 밖에 근로자 전체에 적용되는 사항은 별도 정한다",
		}
		result = self.mod.check_required_items(rules_outline)
		self.assertEqual(result["missing"], [])
		self.assertEqual(len(result["covered"]), 14)
		self.assertEqual(result["coverage_ratio"], 1.0)

	def test_check_required_items_flags_missing_11_and_9의2(self):
		rules_outline = {
			"1": "업무의 시작과 종료 시각은 09:00부터 18:00, 휴게시간은 12시부터 13시, 휴일은 주휴일, 연차휴가, 교대근로 규정",
			"2": "임금은 매월 25일 지급하며 산정기간은 전월 1일부터 말일까지, 계산방법은 별도 규정, 승급은 매년 1회",
		}
		result = self.mod.check_required_items(rules_outline)
		missing_hos = {item["ho"] for item in result["missing"]}
		self.assertIn("11", missing_hos)
		self.assertIn("9의2", missing_hos)
		self.assertLess(result["coverage_ratio"], 1.0)
		self.assertEqual(len(result["covered"]) + len(result["missing"]), 14)

	def test_check_required_items_accepts_list_input(self):
		rules_outline = [
			"직장 내 괴롭힘 예방 교육을 실시하고 발생 시 조사 등 조치를 취한다",
			"표창 및 제재에 관한 사항은 별도 규정에 따른다",
		]
		result = self.mod.check_required_items(rules_outline)
		covered_hos = {item["ho"] for item in result["covered"]}
		self.assertIn("11", covered_hos)
		self.assertIn("12", covered_hos)

	def test_check_required_items_rejects_bad_type(self):
		with self.assertRaises(TypeError):
			self.mod.check_required_items("not a dict or list")


class TestFilingObligation(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()

	def test_ten_or_more_requires_filing(self):
		result = self.mod.filing_obligation(10)
		self.assertTrue(result["required"])
		self.assertEqual(result["legal_basis"], "근로기준법 제93조")

	def test_below_ten_not_required(self):
		result = self.mod.filing_obligation(9)
		self.assertFalse(result["required"])

	def test_negative_headcount_rejected(self):
		with self.assertRaises(ValueError):
			self.mod.filing_obligation(-1)


class TestAmendmentProcedure(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()

	def test_non_disadvantageous_requires_opinion_hearing_only(self):
		result = self.mod.amendment_procedure(is_disadvantageous=False)
		self.assertEqual(result["requirement"], "opinion_hearing")
		self.assertEqual(result["legal_basis"], "근로기준법 제94조제1항")
		self.assertGreaterEqual(len(result["steps"]), 2)

	def test_disadvantageous_requires_consent(self):
		result = self.mod.amendment_procedure(is_disadvantageous=True)
		self.assertEqual(result["requirement"], "consent")
		self.assertIn("동의", " ".join(result["steps"]))

	def test_majority_union_named_as_subject(self):
		result = self.mod.amendment_procedure(is_disadvantageous=False, has_majority_union=True)
		self.assertIn("과반수 노동조합", result["subject"])

	def test_no_majority_union_subject_is_employee_majority(self):
		result = self.mod.amendment_procedure(is_disadvantageous=True, has_majority_union=False)
		self.assertIn("근로자 과반수", result["subject"])

	def test_filing_requires_written_opinion_attached(self):
		result = self.mod.amendment_procedure(is_disadvantageous=False)
		joined = " ".join(result["steps"])
		self.assertIn("서면", joined)


class TestClassifyAmendment(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()

	def test_wage_increase_is_favorable_candidate(self):
		result = self.mod.classify_amendment(old_item=2000000, new_item=2200000, kind="higher_is_favorable")
		self.assertEqual(result["candidate"], "favorable")
		self.assertTrue(result["requires_labor_attorney_review"])

	def test_wage_decrease_is_unfavorable_candidate(self):
		result = self.mod.classify_amendment(old_item=2000000, new_item=1800000, kind="higher_is_favorable")
		self.assertEqual(result["candidate"], "unfavorable")

	def test_workday_decrease_favorable_when_lower_is_favorable(self):
		# 예: 소정근로시간 단축 등 "낮을수록 유리"한 항목
		result = self.mod.classify_amendment(old_item=45, new_item=40, kind="lower_is_favorable")
		self.assertEqual(result["candidate"], "favorable")

	def test_equal_values_are_neutral(self):
		result = self.mod.classify_amendment(old_item=15, new_item=15, kind="higher_is_favorable")
		self.assertEqual(result["candidate"], "neutral")

	def test_non_numeric_values_are_indeterminate(self):
		result = self.mod.classify_amendment(
			old_item="연차는 근로기준법에 따른다",
			new_item="연차는 회사가 정하는 바에 따른다",
			kind="higher_is_favorable",
		)
		self.assertEqual(result["candidate"], "indeterminate")
		self.assertTrue(result["requires_labor_attorney_review"])

	def test_unknown_kind_rejected(self):
		with self.assertRaises(ValueError):
			self.mod.classify_amendment(old_item=1, new_item=2, kind="bogus")

	def test_never_asserts_disadvantage_determination(self):
		# 설계서 §8: 단정 금지 — 항상 review 플래그가 True여야 한다.
		for kind, old, new in (
			("higher_is_favorable", 100, 200),
			("higher_is_favorable", 200, 100),
			("lower_is_favorable", 40, 45),
		):
			result = self.mod.classify_amendment(old_item=old, new_item=new, kind=kind)
			self.assertTrue(result["requires_labor_attorney_review"])
			self.assertNotIn("is_disadvantageous", result)


if __name__ == "__main__":
	unittest.main()
