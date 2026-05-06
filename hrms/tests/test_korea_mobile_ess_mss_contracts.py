#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import importlib.util
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "mobile_ess_mss.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_mobile_ess_mss", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


class TestKoreaMobileEssMssContracts(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()
		self.period = {"start_date": "2026-05-01", "end_date": "2026-05-31"}

	def test_builds_employee_mobile_home_from_employee_scoped_records(self):
		home = self.mod.build_mobile_employee_home(
			employee="EMP-001",
			period=self.period,
			records=[
				{"record_type": "attendance", "employee": "EMP-001", "status": "Checked In", "workplace": "SEOUL-01"},
				{"record_type": "leave_balance", "employee": "EMP-001", "leave_type": "Annual Leave", "remaining_days": 7},
				{"record_type": "payslip", "employee": "EMP-001", "name": "SAL-001", "status": "Available"},
				{"record_type": "leave_balance", "employee": "EMP-002", "leave_type": "Annual Leave", "remaining_days": 99},
			],
		)

		self.assertEqual(home["contract_type"], "korea_mobile_ess_home_v1")
		self.assertEqual(home["employee"], "EMP-001")
		self.assertEqual(home["period"], self.period)
		self.assertEqual(home["attendance_status"], {"status": "Checked In", "workplace": "SEOUL-01"})
		self.assertEqual(home["leave_balances"], [{"leave_type": "Annual Leave", "remaining_days": 7}])
		self.assertEqual(home["payslips"], [{"name": "SAL-001", "status": "Available"}])
		self.assertEqual([action["action"] for action in home["quick_actions"]], ["request_leave", "view_payslip"])
		self.assertTrue(all(action["requires_runtime_apply"] for action in home["quick_actions"]))

	def test_builds_manager_mobile_worklist_filtered_by_manager_workplace_and_open_status(self):
		worklist = self.mod.build_mobile_manager_worklist(
			manager="MGR-001",
			period=self.period,
			workplace="SEOUL-01",
			today=dt.date(2026, 5, 10),
			records=[
				{
					"doctype": "Leave Application",
					"name": "LA-1",
					"employee": "EMP-001",
					"manager": "MGR-001",
					"workplace": "SEOUL-01",
					"status": "Pending",
					"posting_date": "2026-05-04",
				},
				{
					"doctype": "Expense Claim",
					"name": "EXP-1",
					"employee": "EMP-002",
					"manager": "MGR-001",
					"workplace": "BUSAN-01",
					"status": "Pending",
					"posting_date": "2026-05-01",
				},
				{
					"doctype": "Attendance Request",
					"name": "ATT-1",
					"employee": "EMP-003",
					"manager": "MGR-002",
					"workplace": "SEOUL-01",
					"status": "Pending",
					"posting_date": "2026-05-02",
				},
			],
		)

		self.assertEqual(worklist["contract_type"], "korea_mobile_mss_worklist_v1")
		self.assertEqual(worklist["manager"], "MGR-001")
		self.assertEqual(worklist["workplace"], "SEOUL-01")
		self.assertEqual(worklist["summary"], {"total": 1, "overdue": 1, "by_doctype": {"Leave Application": 1}})
		self.assertEqual(worklist["items"][0]["name"], "LA-1")
		self.assertEqual(worklist["items"][0]["priority"], "High")
		self.assertEqual(worklist["items"][0]["action"], {"action": "review_approval", "enabled": True, "requires_runtime_apply": True})

	def test_manager_worklist_filters_records_to_period_and_requires_explicit_today(self):
		with self.assertRaisesRegex(ValueError, "today is required"):
			self.mod.build_mobile_manager_worklist(manager="MGR-001", period=self.period, workplace="SEOUL-01", records=[])

		worklist = self.mod.build_mobile_manager_worklist(
			manager="MGR-001",
			period=self.period,
			workplace="SEOUL-01",
			today=dt.date(2026, 6, 10),
			records=[
				{"doctype": "Leave Application", "name": "APRIL", "employee": "EMP-001", "manager": "MGR-001", "workplace": "SEOUL-01", "status": "Pending", "posting_date": "2026-04-30"},
				{"doctype": "Leave Application", "name": "MAY", "employee": "EMP-001", "manager": "MGR-001", "workplace": "SEOUL-01", "status": "Pending", "posting_date": "2026-05-01"},
				{"doctype": "Leave Application", "name": "JUNE", "employee": "EMP-001", "manager": "MGR-001", "workplace": "SEOUL-01", "status": "Pending", "posting_date": "2026-06-01"},
			],
		)

		self.assertEqual([item["name"] for item in worklist["items"]], ["MAY"])

	def test_manager_worklist_rejects_bool_non_integral_and_int_subclass_overdue_controls(self):
		class IntSubclass(int):
			pass

		for invalid_value in (True, False, 2.5, "3", IntSubclass(3)):
			with self.subTest(invalid_value=invalid_value):
				with self.assertRaisesRegex(ValueError, "overdue_after_days must be an integer"):
					self.mod.build_mobile_manager_worklist(
						manager="MGR-001",
						period=self.period,
						workplace="SEOUL-01",
						today=dt.date(2026, 5, 10),
						overdue_after_days=invalid_value,
						records=[],
					)

	def test_rejects_invalid_period_non_numeric_leave_balance_missing_actor_and_future_posting(self):
		with self.assertRaisesRegex(ValueError, "period.start_date cannot be after period.end_date"):
			self.mod.build_mobile_employee_home(employee="EMP-001", period={"start_date": "2026-06-01", "end_date": "2026-05-31"}, records=[])

		with self.assertRaisesRegex(ValueError, "remaining_days must be finite"):
			self.mod.build_mobile_employee_home(
				employee="EMP-001",
				period=self.period,
				records=[{"record_type": "leave_balance", "employee": "EMP-001", "leave_type": "Annual Leave", "remaining_days": float("nan")}],
			)

		home = self.mod.build_mobile_employee_home(
			employee="EMP-001",
			period=self.period,
			records=[{"record_type": "leave_balance", "employee": "EMP-001", "leave_type": "Annual Leave", "remaining_days": "1.5"}],
		)
		self.assertEqual(home["leave_balances"][0]["remaining_days"], 1.5)

		with self.assertRaisesRegex(ValueError, "manager is required"):
			self.mod.build_mobile_manager_worklist(manager="", period=self.period, workplace="SEOUL-01", today=dt.date(2026, 5, 10), records=[])

		with self.assertRaisesRegex(ValueError, "record.posting_date cannot be after today"):
			self.mod.build_mobile_manager_worklist(
				manager="MGR-001",
				period=self.period,
				workplace="SEOUL-01",
				today=dt.date(2026, 5, 10),
				records=[{"doctype": "Leave Application", "name": "FUTURE", "employee": "EMP-001", "manager": "MGR-001", "workplace": "SEOUL-01", "status": "Pending", "posting_date": "2026-06-01"}],
			)


if __name__ == "__main__":
	unittest.main()
