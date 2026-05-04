#!/usr/bin/env python3
"""Direct-run tests for Korea compliance checklist MVP."""

from __future__ import annotations

import datetime as dt
import importlib.util
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "compliance_checklist.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_compliance_checklist", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


class TestKoreaComplianceChecklist(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()

	def test_builds_recurring_checklist_with_due_dates_and_owners(self):
		items = self.mod.build_compliance_checklist(
			period_start=dt.date(2026, 5, 1),
			period_end=dt.date(2026, 5, 31),
			owners={"payroll": "HR Payroll", "labor": "HR Ops"},
		)

		codes = [item["code"] for item in items]
		self.assertEqual(codes, ["payroll-close", "payslip-issue", "attendance-archive", "labor-contract-review"])
		self.assertEqual(items[0]["owner"] , "HR Payroll")
		self.assertEqual(items[0]["due_date"], "2026-06-10")
		self.assertEqual(items[3]["owner"], "HR Ops")
		self.assertEqual(items[3]["due_date"], "2026-05-31")

	def test_evaluates_completion_status_and_overdue_flags(self):
		items = self.mod.evaluate_compliance_checklist(
			self.mod.build_compliance_checklist(
				period_start=dt.date(2026, 5, 1),
				period_end=dt.date(2026, 5, 31),
			),
			completed_codes={"payroll-close"},
			today=dt.date(2026, 6, 11),
		)

		self.assertEqual(items[0]["status"], "Completed")
		self.assertEqual(items[1]["status"], "Overdue")
		self.assertEqual(items[2]["status"], "Open")

	def test_checklist_summary_counts_statuses(self):
		items = [
			{"status": "Completed"},
			{"status": "Open"},
			{"status": "Overdue"},
			{"status": "Overdue"},
		]

		self.assertEqual(self.mod.summarize_checklist(items), {"Completed": 1, "Open": 1, "Overdue": 2})

	def test_invalid_period_is_rejected(self):
		with self.assertRaises(ValueError):
			self.mod.build_compliance_checklist(period_start=dt.date(2026, 6, 1), period_end=dt.date(2026, 5, 31))


if __name__ == "__main__":
	unittest.main()
