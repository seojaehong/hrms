#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import pathlib
import sys
import types
import unittest
from types import SimpleNamespace

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "demo_seed.py"


def load_module_with_frappe_stub():
	previous_frappe = sys.modules.get("frappe")
	previous_frappe_utils = sys.modules.get("frappe.utils")
	frappe_stub = types.ModuleType("frappe")
	frappe_stub.utils = types.ModuleType("frappe.utils")
	frappe_stub.utils.getdate = lambda value: value
	sys.modules["frappe"] = frappe_stub
	sys.modules["frappe.utils"] = frappe_stub.utils
	try:
		spec = importlib.util.spec_from_file_location("korea_demo_seed", MODULE_PATH)
		module = importlib.util.module_from_spec(spec)
		assert spec.loader is not None
		spec.loader.exec_module(module)
		return module
	finally:
		if previous_frappe is None:
			sys.modules.pop("frappe", None)
		else:
			sys.modules["frappe"] = previous_frappe
		if previous_frappe_utils is None:
			sys.modules.pop("frappe.utils", None)
		else:
			sys.modules["frappe.utils"] = previous_frappe_utils


class TestKoreaDemoSeedBlockerRealism(unittest.TestCase):
	def setUp(self):
		self.mod = load_module_with_frappe_stub()

	def test_demo_blocker_seed_creates_idempotent_unsubmitted_runtime_rows(self):
		calls = []

		def fake_ensure_doc(doctype, name=None, filters=None, values=None):
			calls.append({"doctype": doctype, "name": name, "filters": filters, "values": dict(values or {})})
			return SimpleNamespace(name=name or f"{doctype}-EXISTING"), not any(
				call["doctype"] == doctype and call["name"] == name for call in calls[:-1]
			)

		self.mod.ensure_doc = fake_ensure_doc
		employees = [
			SimpleNamespace(name="HR-EMP-0001", work_location_name="서울 본사"),
			SimpleNamespace(name="HR-EMP-0002", work_location_name="강남 매장"),
		]

		first = self.mod.ensure_demo_blocker_transactions(company="노란봉투법 데모", employees=employees)
		second = self.mod.ensure_demo_blocker_transactions(company="노란봉투법 데모", employees=employees)

		self.assertEqual(first, second)
		self.assertEqual(first["runtime_action"], "demo_seed_only")
		self.assertEqual(first["mutation_boundary"], "demo_seed_idempotent_no_submit_no_approve_no_send_no_provider_call")
		self.assertEqual(first["ai_role"], "assistant_only")
		self.assertFalse(first["requires_runtime_apply"])
		self.assertEqual(
			{row["doctype"] for row in first["blocker_rows"]},
			{"Attendance", "Overtime Slip", "Expense Claim"},
		)
		self.assertTrue(all(row["docstatus"] == 0 for row in first["blocker_rows"]))
		self.assertTrue(all(row["workplace"] in {"서울 본사", "강남 매장"} for row in first["blocker_rows"]))

		attendance_call = next(call for call in calls if call["doctype"] == "Attendance")
		self.assertEqual(attendance_call["values"]["naming_series"], "HR-ATT-.YYYY.-")
		self.assertEqual(attendance_call["values"]["status"], "Absent")
		self.assertEqual(attendance_call["values"]["docstatus"], 0)
		self.assertEqual(attendance_call["values"]["company"], "노란봉투법 데모")

		overtime_call = next(call for call in calls if call["doctype"] == "Overtime Slip")
		self.assertEqual(overtime_call["values"]["posting_date"], "2026-05-31")
		self.assertEqual(overtime_call["values"]["start_date"], "2026-05-01")
		self.assertEqual(overtime_call["values"]["end_date"], "2026-05-31")
		self.assertEqual(overtime_call["values"]["total_overtime_duration"], 2.5)
		self.assertEqual(overtime_call["values"]["docstatus"], 0)
		self.assertEqual(
			overtime_call["values"]["overtime_details"],
			[
				{
					"date": "2026-05-22",
					"overtime_type": "KR Demo Overtime Review",
					"overtime_duration": 2.5,
					"standard_working_hours": 8,
				}
			],
		)

		expense_type_call = next(call for call in calls if call["doctype"] == "Expense Claim Type")
		self.assertEqual(
			expense_type_call["values"]["accounts"],
			[
				{
					"company": "노란봉투법 데모",
					"default_account": "Administrative Expenses - NBG",
				}
			],
		)

		expense_call = next(call for call in calls if call["doctype"] == "Expense Claim")
		self.assertEqual(expense_call["values"]["naming_series"], "HR-EXP-.YYYY.-")
		self.assertEqual(expense_call["values"]["approval_status"], "Draft")
		self.assertEqual(expense_call["values"]["currency"], "KRW")
		self.assertEqual(expense_call["values"]["exchange_rate"], 1)
		self.assertEqual(expense_call["values"]["docstatus"], 0)
		self.assertEqual(expense_call["values"]["total_claimed_amount"], 86000)
		self.assertEqual(
			expense_call["values"]["expenses"],
			[
				{
					"expense_date": "2026-05-27",
					"expense_type": "KR Demo Meal Transport",
					"description": "Payroll-close demo unsettled meal and transport claim",
					"amount": 86000,
					"sanctioned_amount": 0,
				}
			],
		)

	def test_demo_blocker_seed_rejects_missing_employee_context(self):
		with self.assertRaisesRegex(ValueError, "at least two demo employees"):
			self.mod.ensure_demo_blocker_transactions(company="노란봉투법 데모", employees=[])

		with self.assertRaisesRegex(ValueError, "employee.name must be a non-empty string"):
			self.mod.ensure_demo_blocker_transactions(
				company="노란봉투법 데모",
				employees=[SimpleNamespace(name="", work_location_name="서울 본사"), SimpleNamespace(name="HR-EMP-0002")],
			)


if __name__ == "__main__":
	unittest.main()
