# -*- coding: utf-8 -*-
"""취업규칙 점검 API 래퍼 테스트 — framework-free. TDD: RED 먼저.

work_rules_api는 코어(work_rules)에 위임하며,
- check_required_items_api: 커버 항목 리스트 표본 → covered/missing/coverage_ratio 코어 일치
- amendment_procedure_api: §94 절차 + filing_obligation(§93 신고의무) 포함 반환
- list_required_items_api: 14개 필수항목 + 체크박스용 고유 marker(1:1 커버리지 보장)

실행: python3 hrms/tests/test_korea_work_rules_api.py
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


_api = _load("work_rules_api")
_core = _load("work_rules")

# 커버 항목 리스트 표본 — 임금·퇴직·괴롭힘·안전보건만 규정된 취업규칙 개요
_SAMPLE_OUTLINE = [
	"제4조 임금의 결정과 지급 방법, 산정기간",
	"제10조 퇴직에 관한 사항",
	"제12조 직장 내 괴롭힘의 예방 및 조치",
	"제15조 안전과 보건",
]


class TestCheckRequiredItemsApi(unittest.TestCase):
	def test_matches_core_list_sample(self):
		api_result = _api.check_required_items_api(_SAMPLE_OUTLINE)
		core_result = _core.check_required_items(_SAMPLE_OUTLINE)
		self.assertEqual(api_result, core_result)
		covered_ho = [c["ho"] for c in api_result["covered"]]
		self.assertIn("2", covered_ho)
		self.assertIn("4", covered_ho)
		self.assertIn("11", covered_ho)
		self.assertIn("9", covered_ho)
		missing_ho = [m["ho"] for m in api_result["missing"]]
		self.assertIn("3", missing_ho)  # 가족수당 누락
		self.assertAlmostEqual(
			api_result["coverage_ratio"], core_result["coverage_ratio"]
		)

	def test_matches_core_dict_sample(self):
		outline = {"2": "임금의 지급", "12": "표창과 징계"}
		self.assertEqual(
			_api.check_required_items_api(outline),
			_core.check_required_items(outline),
		)

	def test_accepts_json_string(self):
		"""Frappe RPC가 리스트/딕셔너리를 JSON 문자열로 전달하는 경우도 허용."""
		self.assertEqual(
			_api.check_required_items_api(json.dumps(_SAMPLE_OUTLINE)),
			_core.check_required_items(_SAMPLE_OUTLINE),
		)

	def test_json_safe(self):
		json.dumps(_api.check_required_items_api(_SAMPLE_OUTLINE))


class TestAmendmentProcedureApi(unittest.TestCase):
	def test_disadvantageous_consent_with_filing(self):
		result = _api.amendment_procedure_api(True, 25)
		core = _core.amendment_procedure(True)
		self.assertEqual(result["requirement"], "consent")
		self.assertEqual(result["steps"], core["steps"])
		self.assertEqual(result["subject"], core["subject"])
		# §93 신고의무 포함 반환
		self.assertEqual(result["filing_obligation"], _core.filing_obligation(25))
		self.assertTrue(result["filing_obligation"]["required"])

	def test_not_disadvantageous_opinion_hearing(self):
		result = _api.amendment_procedure_api(False, 8)
		self.assertEqual(result["requirement"], "opinion_hearing")
		self.assertFalse(result["filing_obligation"]["required"])

	def test_string_inputs(self):
		"""Frappe RPC는 불리언을 'true'/'0', 정수를 문자열로 줄 수 있음."""
		result = _api.amendment_procedure_api("true", "12")
		self.assertEqual(result["requirement"], "consent")
		self.assertEqual(result["filing_obligation"]["headcount"], 12)
		result2 = _api.amendment_procedure_api("0", "9")
		self.assertEqual(result2["requirement"], "opinion_hearing")
		self.assertFalse(result2["filing_obligation"]["required"])

	def test_majority_union_optional(self):
		result = _api.amendment_procedure_api(True, 30, has_majority_union="true")
		self.assertEqual(
			result["subject"],
			_core.amendment_procedure(True, has_majority_union=True)["subject"],
		)

	def test_json_safe(self):
		json.dumps(_api.amendment_procedure_api(True, 15))


class TestListRequiredItemsApi(unittest.TestCase):
	def test_fourteen_items_with_keys(self):
		items = _api.list_required_items_api()
		self.assertEqual(len(items), 14)
		for item in items:
			self.assertIn("ho", item)
			self.assertIn("label", item)
			self.assertIn("marker", item)
		json.dumps(items)

	def test_marker_covers_exactly_one_item(self):
		"""체크박스 UI 계약: 항목 하나의 marker만 보내면 그 항목만 커버된다(교차 매칭 없음)."""
		items = _api.list_required_items_api()
		for item in items:
			result = _core.check_required_items([item["marker"]])
			covered_ho = [c["ho"] for c in result["covered"]]
			self.assertEqual(covered_ho, [item["ho"]], f"marker {item['marker']!r} 교차 매칭")

	def test_all_markers_cover_everything(self):
		items = _api.list_required_items_api()
		result = _core.check_required_items([i["marker"] for i in items])
		self.assertEqual(result["missing"], [])
		self.assertEqual(result["coverage_ratio"], 1.0)


if __name__ == "__main__":
	unittest.main()
