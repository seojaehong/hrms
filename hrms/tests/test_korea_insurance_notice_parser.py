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


if __name__ == "__main__":
	unittest.main()
