# -*- coding: utf-8 -*-
"""고지 대사 API 테스트 — FakeFrappe 스텁, framework-free.

실행: python3 hrms/tests/test_korea_insurance_reconciliation_api.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import sys
import tempfile
import types
import unittest

MODULE_PATH = (
	pathlib.Path(__file__).resolve().parents[1]
	/ "regional"
	/ "south_korea"
	/ "insurance_reconciliation_api.py"
)


class FakeFrappe(types.ModuleType):
	def __init__(self, slips, details, employees=None):
		super().__init__("frappe")
		self._slips = slips
		self._details = details
		self._employees = employees or []
		self.filters_seen = {}

	def whitelist(self):
		return lambda fn: fn

	def get_all(self, doctype, filters=None, fields=None, **kw):
		self.filters_seen[doctype] = filters
		if doctype == "Salary Slip":
			return [dict(s) for s in self._slips]
		if doctype == "Salary Detail":
			parents = set((filters or {}).get("parent", [None, []])[1])
			return [dict(d) for d in self._details if d["parent"] in parents]
		if doctype == "Employee":
			return [dict(e) for e in self._employees]
		return []


def _load(slips, details, employees=None):
	fake = FakeFrappe(slips, details, employees)
	sys.modules["frappe"] = fake
	spec = importlib.util.spec_from_file_location("ins_recon_api_stub", MODULE_PATH)
	mod = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(mod)
	return mod, fake


SLIPS = [
	{"name": "SS-1", "employee": "천시원", "employee_name": "천시원"},
	{"name": "SS-2", "employee": "김하늘", "employee_name": "김하늘"},
]
DETAILS = [
	{"parent": "SS-1", "salary_component": "국민연금", "amount": 187730},
	{"parent": "SS-1", "salary_component": "소득세", "amount": 50000},
	{"parent": "SS-2", "salary_component": "국민연금", "amount": 90000},
	{"parent": "SS-2", "salary_component": "고용보험", "amount": 27000},
]


class TestReconcilePeriod(unittest.TestCase):
	def setUp(self):
		self.mod, self.fake = _load(SLIPS, DETAILS)

	def test_kuukuu_overdeduction_flagged(self):
		notified = [
			{"employee": "천시원", "national_pension": 166500},
			{"employee": "김하늘", "national_pension": 90000, "employment_insurance": 27000},
		]
		out = self.mod.reconcile_period_contributions(2026, 6, notified)
		self.assertEqual(out["period"], "2026-06")
		self.assertEqual(out["employee_count"], 2)
		recon = out["reconciliation"]
		self.assertFalse(recon["ok"])
		self.assertEqual(len(recon["diffs"]), 1)
		self.assertEqual(recon["diffs"][0]["delta"], 21230)
		self.assertIn("+21,230", out["summary_ko"])
		# 소득세는 4대 아님 → unmapped 정보
		self.assertEqual(out["unmapped_deductions"][0]["component"], "소득세")

	def test_notified_json_string_accepted(self):
		notified = json.dumps([
			{"employee": "천시원", "national_pension": 187730},
			{"employee": "김하늘", "national_pension": 90000},
		])
		out = self.mod.reconcile_period_contributions("2026", "6", notified)
		self.assertTrue(out["reconciliation"]["ok"])

	def test_month_bounds_filter(self):
		self.mod.reconcile_period_contributions(2026, 2, [])
		f = self.fake.filters_seen["Salary Slip"]
		self.assertEqual(f["start_date"], ["between", ["2026-02-01", "2026-02-28"]])
		self.assertEqual(f["docstatus"], 1)

	def test_company_filter(self):
		self.mod.reconcile_period_contributions(2026, 6, [], company="노호")
		self.assertEqual(self.fake.filters_seen["Salary Slip"].get("company"), "노호")

	def test_invalid_month_rejected(self):
		with self.assertRaises(ValueError):
			self.mod.reconcile_period_contributions(2026, 13, [])

	def test_notified_must_be_list(self):
		with self.assertRaises(ValueError):
			self.mod.reconcile_period_contributions(2026, 6, {"employee": "x"})


def _write_fixture_xlsx(grid):
	"""grid(행별 셀 리스트)을 tempfile xlsx로 쓰고 경로 반환."""
	from openpyxl import Workbook

	fd, path = tempfile.mkstemp(suffix=".xlsx")
	os.close(fd)
	wb = Workbook()
	ws = wb.active
	for row in grid:
		ws.append(row)
	wb.save(path)
	wb.close()
	return path


FILE_SLIPS = [
	{"name": "SS-1", "employee": "HR-EMP-001", "employee_name": "천시원"},
	{"name": "SS-2", "employee": "HR-EMP-002", "employee_name": "김하늘"},
]
FILE_DETAILS = [
	{"parent": "SS-1", "salary_component": "국민연금", "amount": 187730},
	{"parent": "SS-2", "salary_component": "국민연금", "amount": 90000},
]
EMPLOYEES = [
	{"name": "HR-EMP-001", "employee_name": "천시원", "rrn_masked": "900101-1******"},
	{"name": "HR-EMP-002", "employee_name": "김하늘", "rrn_masked": "920202-2******"},
]


class TestReconcileFromNoticeFile(unittest.TestCase):
	def setUp(self):
		self.mod, self.fake = _load(FILE_SLIPS, FILE_DETAILS, EMPLOYEES)
		self._paths = []

	def tearDown(self):
		for p in self._paths:
			try:
				os.remove(p)
			except OSError:
				pass

	def _fixture(self, grid):
		path = _write_fixture_xlsx(grid)
		self._paths.append(path)
		return path

	def test_end_to_end_rrn_and_name_match(self):
		# A열 match_key(주민번호/이름), B열 국민연금 고지액
		path = self._fixture([
			["매칭키", "국민연금"],
			["900101-1234567", "166,500 원"],  # 주민번호 매칭 → 천시원, 과다공제
			["김하늘", 90000],  # 이름 매칭 → 김하늘, 일치
		])
		column_map = {"match_key": "A", "national_pension": "B"}
		out = self.mod.reconcile_period_from_notice_file(
			2026, 6, path, column_map
		)
		self.assertEqual(out["period"], "2026-06")
		recon = out["reconciliation"]
		self.assertFalse(recon["ok"])
		self.assertEqual(len(recon["diffs"]), 1)
		self.assertEqual(recon["diffs"][0]["employee"], "HR-EMP-001")
		self.assertEqual(recon["diffs"][0]["delta"], 21230)
		self.assertEqual(out["parse_errors"], [])
		self.assertEqual(out["unmatched"], [])
		self.assertEqual(out["ambiguous"], [])

	def test_column_map_json_string(self):
		path = self._fixture([
			["매칭키", "국민연금"],
			["천시원", 187730],
			["김하늘", 90000],
		])
		out = self.mod.reconcile_period_from_notice_file(
			"2026", "6", path, json.dumps({"match_key": "A", "national_pension": "B"})
		)
		self.assertTrue(out["reconciliation"]["ok"])

	def test_unmatched_and_parse_errors_passed_through(self):
		path = self._fixture([
			["매칭키", "국민연금"],
			["없는사람", 12345],  # 매칭 실패 → unmatched
			["천시원", "삼백원"],  # 금액 파싱 불가 → parse_errors
		])
		column_map = {"match_key": "A", "national_pension": "B"}
		out = self.mod.reconcile_period_from_notice_file(2026, 6, path, column_map)
		self.assertEqual(len(out["unmatched"]), 1)
		self.assertEqual(out["unmatched"][0]["match_key"], "없는사람")
		self.assertEqual(len(out["parse_errors"]), 1)
		self.assertEqual(out["parse_errors"][0]["value"], "삼백원")

	def test_ambiguous_homonym(self):
		fake_emps = EMPLOYEES + [
			{"name": "HR-EMP-003", "employee_name": "김하늘", "rrn_masked": "930303-1******"},
		]
		self.mod, self.fake = _load(FILE_SLIPS, FILE_DETAILS, fake_emps)
		path = self._fixture([
			["매칭키", "국민연금"],
			["김하늘", 90000],  # 동명이인 2명 → ambiguous
		])
		column_map = {"match_key": "A", "national_pension": "B"}
		out = self.mod.reconcile_period_from_notice_file(2026, 6, path, column_map)
		self.assertEqual(len(out["ambiguous"]), 1)
		self.assertEqual(len(out["ambiguous"][0]["candidates"]), 2)

	def test_employee_company_filter(self):
		path = self._fixture([["매칭키", "국민연금"], ["천시원", 187730]])
		column_map = {"match_key": "A", "national_pension": "B"}
		self.mod.reconcile_period_from_notice_file(
			2026, 6, path, column_map, company="노호"
		)
		self.assertEqual(self.fake.filters_seen["Employee"].get("company"), "노호")

	def test_column_map_must_be_dict(self):
		path = self._fixture([["매칭키"], ["천시원"]])
		with self.assertRaises(ValueError):
			self.mod.reconcile_period_from_notice_file(2026, 6, path, "[1,2,3]")


if __name__ == "__main__":
	unittest.main()
