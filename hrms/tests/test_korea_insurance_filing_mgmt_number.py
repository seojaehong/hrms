# -*- coding: utf-8 -*-
"""insurance_filing_api 관리번호 필터 테스트 — framework-free.

배경(2026-07-10): 한 법인에 사업장 관리번호가 여러 개(본점/지점·상용/일용 분리성립)인
케이스(노호 실사례). 신고서는 관리번호 단위로 나가야 하므로 직원별 소속 필드
Employee.workplace_management_number + management_number 필터를 도입.

실행: python3 hrms/tests/test_korea_insurance_filing_mgmt_number.py
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import types
import unittest

MODULE_PATH = (
	pathlib.Path(__file__).resolve().parents[1]
	/ "regional"
	/ "south_korea"
	/ "insurance_filing_api.py"
)


def _load_api():
	fake = types.ModuleType("frappe")
	fake.whitelist = lambda: (lambda fn: fn)
	sys.modules.setdefault("frappe", fake)
	spec = importlib.util.spec_from_file_location("ins_api_mgmt_test", MODULE_PATH)
	mod = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(mod)
	return mod


_mod = _load_api()

EMPLOYEES = [
	{"name": "E1", "workplace_management_number": "11122233340"},
	{"name": "E2", "workplace_management_number": "11122233340"},
	{"name": "E3", "workplace_management_number": "55566677780"},
	{"name": "E4", "workplace_management_number": ""},      # 미배정
	{"name": "E5"},                                          # 필드 자체 없음
	{"name": "E6", "workplace_management_number": " 11122233340 "},  # 공백 낀 입력
]


class TestFilterByManagementNumber(unittest.TestCase):
	def test_exact_match_group(self):
		out = _mod._filter_by_management_number(EMPLOYEES, "11122233340")
		self.assertEqual([e["name"] for e in out], ["E1", "E2", "E6"])

	def test_other_group(self):
		out = _mod._filter_by_management_number(EMPLOYEES, "55566677780")
		self.assertEqual([e["name"] for e in out], ["E3"])

	def test_unassigned_excluded(self):
		# 미배정(공백/필드없음) 직원은 어떤 관리번호 필터에도 포함되지 않는다 (오소속 신고 방지)
		for target in ("11122233340", "55566677780"):
			names = [e["name"] for e in _mod._filter_by_management_number(EMPLOYEES, target)]
			self.assertNotIn("E4", names)
			self.assertNotIn("E5", names)

	def test_whitespace_tolerant_target(self):
		out = _mod._filter_by_management_number(EMPLOYEES, " 55566677780 ")
		self.assertEqual([e["name"] for e in out], ["E3"])

	def test_no_match_empty(self):
		self.assertEqual(_mod._filter_by_management_number(EMPLOYEES, "99999999999"), [])


class TestGenerateSignature(unittest.TestCase):
	def test_management_number_param_exists_and_optional(self):
		import inspect

		sig = inspect.signature(_mod.generate_insurance_filing)
		self.assertIn("management_number", sig.parameters)
		self.assertIsNone(sig.parameters["management_number"].default)  # 미지정=기존 동작

	def test_blocked_before_any_query_with_mgmt_number(self):
		# fail-closed 불변식: human_approved 없으면 관리번호를 줘도 조회·생성 없이 blocked
		out = _mod.generate_insurance_filing(
			"acquisition", 2026, 6, "/tmp/nonexistent.xlsx",
			human_approved=False, management_number="11122233340",
		)
		self.assertEqual(out["status"], "blocked")


if __name__ == "__main__":
	unittest.main()
