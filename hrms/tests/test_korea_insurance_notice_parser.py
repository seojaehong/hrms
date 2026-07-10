# -*- coding: utf-8 -*-
"""공단 고지 xlsx 파서 테스트 — framework-free.

fixture xlsx를 openpyxl로 tempfile에 직접 생성해 검증한다.

실행: python3 hrms/tests/test_korea_insurance_notice_parser.py
"""
from __future__ import annotations

import importlib.util
import os
import pathlib
import tempfile
import unittest

_MODULE_PATH = (
	pathlib.Path(__file__).resolve().parents[1]
	/ "regional"
	/ "south_korea"
	/ "insurance_notice_parser.py"
)
_spec = importlib.util.spec_from_file_location("ins_notice_parser", _MODULE_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

parse_notice_xlsx = _mod.parse_notice_xlsx
match_notice_to_employees = _mod.match_notice_to_employees


def _write_xlsx(rows: list[list]) -> str:
	"""rows(행별 셀 리스트)를 임시 xlsx로 쓰고 경로 반환."""
	from openpyxl import Workbook

	wb = Workbook()
	ws = wb.active
	for r in rows:
		ws.append(r)
	fd, path = tempfile.mkstemp(suffix=".xlsx")
	os.close(fd)
	wb.save(path)
	return path


class TestParseNotice(unittest.TestCase):
	def setUp(self):
		self._paths: list[str] = []

	def tearDown(self):
		for p in self._paths:
			try:
				os.remove(p)
			except OSError:
				pass

	def _fixture(self, rows):
		path = _write_xlsx(rows)
		self._paths.append(path)
		return path

	def test_basic_parse_with_comma_and_won(self):
		path = self._fixture([
			["번호", "이름", "국민연금", "건강보험"],          # header (row 1)
			[1, "천시원", "166,500", "131,160 원"],           # row 2
			[2, "김철수", 90000, "70,900"],                    # row 3 (숫자 셀 처리)
		])
		out = parse_notice_xlsx(
			path,
			{"match_key": "B", "national_pension": "C", "health_insurance": "D"},
		)
		self.assertEqual(out["errors"], [])
		self.assertEqual(out["rows"], [
			{"match_key": "천시원", "national_pension": 166500, "health_insurance": 131160},
			{"match_key": "김철수", "national_pension": 90000, "health_insurance": 70900},
		])

	def test_empty_rows_skipped(self):
		path = self._fixture([
			["이름", "국민연금"],
			["천시원", "166,500"],
			[None, None],              # 완전 빈 행
			["  ", "100"],             # match_key 공백 → skip
			["김철수", "90,000"],
		])
		out = parse_notice_xlsx(path, {"match_key": "A", "national_pension": "B"})
		self.assertEqual([r["match_key"] for r in out["rows"]], ["천시원", "김철수"])
		self.assertEqual(out["errors"], [])

	def test_bad_amount_exposed_in_errors(self):
		path = self._fixture([
			["이름", "국민연금", "건강보험"],
			["천시원", "abc", "131,160"],       # 국민연금 파싱 불가
			["김철수", "90,000", "70,900"],
		])
		out = parse_notice_xlsx(
			path,
			{"match_key": "A", "national_pension": "B", "health_insurance": "C"},
		)
		# 오류 행도 숨기지 않고 rows에 남되, 파싱된 금액만 포함
		self.assertEqual(out["rows"][0], {"match_key": "천시원", "health_insurance": 131160})
		self.assertEqual(out["rows"][1], {"match_key": "김철수", "national_pension": 90000, "health_insurance": 70900})
		self.assertEqual(len(out["errors"]), 1)
		err = out["errors"][0]
		self.assertEqual(err["row"], 2)
		self.assertEqual(err["column"], "B")
		self.assertEqual(err["value"], "abc")
		self.assertIn("숫자", err["reason"])

	def test_header_row_option(self):
		path = self._fixture([
			["보고서 제목", None],           # row 1 (제목)
			["귀속월 2026-05", None],        # row 2 (부제)
			["이름", "국민연금"],            # row 3 (실제 헤더)
			["천시원", "166,500"],           # row 4
		])
		out = parse_notice_xlsx(
			path,
			{"match_key": "A", "national_pension": "B"},
			header_row=3,
		)
		self.assertEqual(out["rows"], [{"match_key": "천시원", "national_pension": 166500}])
		self.assertEqual(out["errors"], [])

	def test_amount_key_only_when_in_column_map(self):
		# column_map에 없는 필드는 rows에 나타나지 않는다.
		path = self._fixture([
			["이름", "국민연금", "건강보험"],
			["천시원", "166,500", "131,160"],
		])
		out = parse_notice_xlsx(path, {"match_key": "A", "national_pension": "B"})
		self.assertEqual(out["rows"], [{"match_key": "천시원", "national_pension": 166500}])

	def test_missing_match_key_in_column_map_rejected(self):
		path = self._fixture([["이름", "국민연금"], ["천시원", "166,500"]])
		with self.assertRaises(ValueError):
			parse_notice_xlsx(path, {"national_pension": "B"})

	def test_empty_amount_cell_omitted(self):
		path = self._fixture([
			["이름", "국민연금", "건강보험"],
			["천시원", "166,500", None],       # 건강보험 빈 셀 → 키 생략(오류 아님)
		])
		out = parse_notice_xlsx(
			path,
			{"match_key": "A", "national_pension": "B", "health_insurance": "C"},
		)
		self.assertEqual(out["rows"], [{"match_key": "천시원", "national_pension": 166500}])
		self.assertEqual(out["errors"], [])


class TestMatchNoticeToEmployees(unittest.TestCase):
	def _employees(self):
		return [
			{"employee": "HR-001", "employee_name": "천시원", "rrn_masked": "900101-1******"},
			{"employee": "HR-002", "employee_name": "김철수", "rrn_masked": "850315-2******"},
		]

	def test_match_by_rrn(self):
		# match_key가 주민번호(하이픈 포함) → rrn_masked 앞 7자리로 매칭
		out = match_notice_to_employees(
			[{"match_key": "900101-1234567", "national_pension": 166500}],
			self._employees(),
		)
		self.assertEqual(out["rows"], [{"employee": "HR-001", "national_pension": 166500}])
		self.assertEqual(out["unmatched"], [])
		self.assertEqual(out["ambiguous"], [])

	def test_match_by_rrn_without_hyphen(self):
		# 하이픈 미포함 13자리도 매칭
		out = match_notice_to_employees(
			[{"match_key": "8503152345678", "health_insurance": 70900}],
			self._employees(),
		)
		self.assertEqual(out["rows"], [{"employee": "HR-002", "health_insurance": 70900}])

	def test_match_by_name(self):
		# 주민번호 형태가 아니면 이름 정확 일치(공백 제거)
		out = match_notice_to_employees(
			[{"match_key": " 천 시원 ", "national_pension": 166500}],
			self._employees(),
		)
		self.assertEqual(out["rows"], [{"employee": "HR-001", "national_pension": 166500}])
		self.assertEqual(out["unmatched"], [])

	def test_ambiguous_duplicate_name(self):
		# 동명이인 → ambiguous, 추측 배정 금지
		emps = [
			{"employee": "HR-010", "employee_name": "이영희"},
			{"employee": "HR-011", "employee_name": "이영희"},
		]
		out = match_notice_to_employees(
			[{"match_key": "이영희", "national_pension": 90000}],
			emps,
		)
		self.assertEqual(out["rows"], [])
		self.assertEqual(len(out["ambiguous"]), 1)
		amb = out["ambiguous"][0]
		self.assertEqual(amb["row"]["match_key"], "이영희")
		self.assertEqual([c["employee"] for c in amb["candidates"]], ["HR-010", "HR-011"])
		self.assertEqual(out["unmatched"], [])

	def test_unmatched(self):
		# 아무에게도 매칭 안 되면 unmatched
		out = match_notice_to_employees(
			[{"match_key": "박존재안함", "national_pension": 50000}],
			self._employees(),
		)
		self.assertEqual(out["rows"], [])
		self.assertEqual(out["ambiguous"], [])
		self.assertEqual(out["unmatched"], [{"match_key": "박존재안함", "national_pension": 50000}])

	def test_employee_without_rrn_masked(self):
		# rrn_masked 없는 직원 — RRN 매칭에선 제외, 이름 매칭은 정상
		emps = [
			{"employee": "HR-020", "employee_name": "정민수"},  # rrn_masked 없음
		]
		# 주민번호로는 매칭 안 됨 → unmatched
		out_rrn = match_notice_to_employees(
			[{"match_key": "900101-1234567", "national_pension": 100}],
			emps,
		)
		self.assertEqual(out_rrn["rows"], [])
		self.assertEqual(len(out_rrn["unmatched"]), 1)
		# 이름으로는 매칭됨
		out_name = match_notice_to_employees(
			[{"match_key": "정민수", "national_pension": 100}],
			emps,
		)
		self.assertEqual(out_name["rows"], [{"employee": "HR-020", "national_pension": 100}])


if __name__ == "__main__":
	unittest.main()
