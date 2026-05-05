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

	def test_builds_compliance_diagnosis_with_evidence_gaps_and_actions(self):
		items = self.mod.evaluate_compliance_checklist(
			self.mod.build_compliance_checklist(
				period_start=dt.date(2026, 5, 1),
				period_end=dt.date(2026, 5, 31),
			),
			completed_codes={"payslip-issue"},
			today=dt.date(2026, 7, 2),
		)

		diagnosis = self.mod.build_compliance_diagnosis(
			items,
			evidence={
				"payslip-issue": ["Salary Slip SAL-2026-05-001"],
				"attendance-archive": [],
			},
			reviewer="Labor Attorney Review Queue",
		)

		self.assertEqual(diagnosis["contract_type"], "korea_compliance_diagnosis_v1")
		self.assertEqual(diagnosis["reviewer"], "Labor Attorney Review Queue")
		self.assertEqual(diagnosis["summary"], {"Completed": 1, "Open": 0, "Overdue": 3})
		self.assertTrue(diagnosis["requires_human_review"])
		self.assertNotIn("score", diagnosis)
		by_code = {finding["code"]: finding for finding in diagnosis["findings"]}
		self.assertEqual(by_code["payroll-close"]["severity"], "critical")
		self.assertEqual(by_code["payroll-close"]["evidence_status"], "missing")
		self.assertEqual(by_code["payslip-issue"]["evidence_status"], "attached")
		self.assertEqual(by_code["attendance-archive"]["action"]["action"], "attach_evidence")
		self.assertTrue(by_code["attendance-archive"]["action"]["requires_runtime_apply"])

	def test_compliance_diagnosis_does_not_escalate_open_items_before_due(self):
		items = self.mod.build_compliance_checklist(
			period_start=dt.date(2026, 5, 1),
			period_end=dt.date(2026, 5, 31),
		)

		diagnosis = self.mod.build_compliance_diagnosis(items, evidence={})

		self.assertFalse(diagnosis["requires_human_review"])
		self.assertTrue(all(finding["severity"] == "ok" for finding in diagnosis["findings"]))
		self.assertTrue(all(not finding["action"]["enabled"] for finding in diagnosis["findings"]))

	def test_compliance_diagnosis_rejects_malformed_evidence_values(self):
		items = self.mod.build_compliance_checklist(
			period_start=dt.date(2026, 5, 1),
			period_end=dt.date(2026, 5, 31),
		)

		with self.assertRaises(TypeError):
			self.mod.build_compliance_diagnosis(items, evidence={"payroll-close": "doc-123"})

		with self.assertRaises(ValueError):
			self.mod.build_compliance_diagnosis(items, evidence={"payroll-close": [" "]})

	def test_compliance_diagnosis_rejects_unknown_evidence_code(self):
		items = self.mod.build_compliance_checklist(
			period_start=dt.date(2026, 5, 1),
			period_end=dt.date(2026, 5, 31),
		)

		with self.assertRaises(ValueError):
			self.mod.build_compliance_diagnosis(items, evidence={"unknown": ["doc"]})

	def test_compliance_diagnosis_rejects_non_dict_items(self):
		with self.assertRaises(TypeError):
			self.mod.build_compliance_diagnosis(["not-a-dict"])

	def test_invalid_period_is_rejected(self):
		with self.assertRaises(ValueError):
			self.mod.build_compliance_checklist(period_start=dt.date(2026, 6, 1), period_end=dt.date(2026, 5, 31))


if __name__ == "__main__":
	unittest.main()
