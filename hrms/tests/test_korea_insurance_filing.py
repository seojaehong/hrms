"""4대보험 신고 자동화 코어 테스트 — framework-free.

실행: python3 hrms/tests/test_korea_insurance_filing.py
"""

from __future__ import annotations

import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "hrms" / "regional" / "south_korea" / "insurance_filing.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_insurance_filing", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


mod = load_module()

EMPLOYEES = [
	{"name": "E1", "employee_name": "김입사", "date_of_joining": "2026-07-15", "monthly_wage": 3000000},
	{"name": "E2", "employee_name": "박기존", "date_of_joining": "2025-01-02"},
	{"name": "E3", "employee_name": "이퇴사", "date_of_joining": "2024-05-01", "relieving_date": "2026-07-20", "loss_reason": "계약만료"},
	{"name": "E4", "employee_name": "최전월퇴사", "date_of_joining": "2024-05-01", "relieving_date": "2026-06-30"},
]


class TestDetect(unittest.TestCase):
	def test_acquisitions_only_in_month(self):
		rows = mod.detect_acquisitions(EMPLOYEES, 2026, 7)
		self.assertEqual([r["employee_name"] for r in rows], ["김입사"])
		self.assertEqual(rows[0]["acquisition_date"], "2026-07-15")
		self.assertEqual(rows[0]["monthly_wage"], 3000000)

	def test_losses_loss_date_is_last_day_plus_one(self):
		rows = mod.detect_losses(EMPLOYEES, 2026, 7)
		self.assertEqual([r["employee_name"] for r in rows], ["이퇴사"])
		self.assertEqual(rows[0]["last_working_date"], "2026-07-20")
		self.assertEqual(rows[0]["loss_date"], "2026-07-21")
		self.assertEqual(rows[0]["loss_reason_code"], "32")

	def test_unknown_reason_falls_back_to_etc(self):
		rows = mod.detect_losses(
			[{"name": "E9", "employee_name": "무사유", "relieving_date": "2026-07-01", "loss_reason": "이상한값"}],
			2026, 7,
		)
		self.assertEqual(rows[0]["loss_reason_code"], "26")


class TestDailyWorkBackfill(unittest.TestCase):
	def test_skill_example_case(self):
		# 스킬 문서 예시: 근무일수=4, 마지막=5 → 2,3,4,5일
		self.assertEqual(mod.mark_daily_work_days(4, 5, 31), [2, 3, 4, 5])

	def test_single_day(self):
		self.assertEqual(mod.mark_daily_work_days(1, 31, 31), [31])

	def test_invalid_ranges_rejected(self):
		with self.assertRaises(ValueError):
			mod.mark_daily_work_days(6, 5, 31)
		with self.assertRaises(ValueError):
			mod.mark_daily_work_days(1, 32, 31)


class TestExtractDailyWorkers(unittest.TestCase):
	DAILY_EMPLOYEES = [
		{"name": "D1", "employee_name": "일용갑", "employment_type": "일용직", "daily_wage": 120000},
		{"name": "D2", "employee_name": "일용을", "employment_type": "일용근로자", "daily_wage": 100000, "total_wage": 500000},
		{"name": "M1", "employee_name": "월급정직원", "employment_type": "정규직", "daily_wage": 0},
	]
	ATTENDANCE = [
		# D1: 7월 3·5·10일 = 3일 (Present/Half Day)
		{"employee": "D1", "attendance_date": "2026-07-03", "status": "Present"},
		{"employee": "D1", "attendance_date": "2026-07-05", "status": "Half Day"},
		{"employee": "D1", "attendance_date": "2026-07-10", "status": "Present"},
		{"employee": "D1", "attendance_date": "2026-07-12", "status": "Absent"},  # 제외(status)
		{"employee": "D1", "attendance_date": "2026-06-30", "status": "Present"},  # 제외(타 월)
		# D2: 7월 1·2일 = 2일
		{"employee": "D2", "attendance_date": "2026-07-01", "status": "Present"},
		{"employee": "D2", "attendance_date": "2026-07-02", "status": "Present"},
		# M1: 근태 있어도 일용직 아님 → 제외
		{"employee": "M1", "attendance_date": "2026-07-04", "status": "Present"},
	]

	def test_aggregates_only_daily_workers_in_month(self):
		rows = mod.extract_daily_workers(self.DAILY_EMPLOYEES, self.ATTENDANCE, 2026, 7)
		self.assertEqual([r["employee_name"] for r in rows], ["일용갑", "일용을"])
		by_name = {r["employee_name"]: r for r in rows}
		# 근무일 정확 집계 + 타 월/비근무 status 제외
		self.assertEqual(by_name["일용갑"]["work_days"], [3, 5, 10])
		self.assertEqual(by_name["일용을"]["work_days"], [1, 2])
		# total_wage: 명시 없으면 daily_wage*근무일수, 있으면 그대로
		self.assertEqual(by_name["일용갑"]["total_wage"], 120000 * 3)
		self.assertEqual(by_name["일용을"]["total_wage"], 500000)

	def test_non_daily_excluded_even_with_attendance(self):
		names = [r["employee_name"] for r in mod.extract_daily_workers(self.DAILY_EMPLOYEES, self.ATTENDANCE, 2026, 7)]
		self.assertNotIn("월급정직원", names)

	def test_no_attendance_worker_dropped(self):
		# 근태 없는 일용직은 결과에서 제외(빈 근무일 신고 금지)
		rows = mod.extract_daily_workers(self.DAILY_EMPLOYEES, [], 2026, 7)
		self.assertEqual(rows, [])


class TestContract(unittest.TestCase):
	def test_contract_requires_human_confirmation(self):
		c = mod.build_filing_contract(filing_type="acquisition", year=2026, month=7, employees=EMPLOYEES)
		self.assertTrue(c["requires_human_confirmation"])
		self.assertEqual(c["candidate_count"], 1)
		self.assertEqual(c["period"], "2026-07")

	def test_invalid_type_rejected(self):
		with self.assertRaises(ValueError):
			mod.build_filing_contract(filing_type="both", year=2026, month=7, employees=[])


if __name__ == "__main__":
	unittest.main()
