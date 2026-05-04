#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "closing_center.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_closing_center", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


class TestKoreaClosingCenter(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()

	def test_builds_workplace_filtered_closing_center_with_blockers_actions_and_drilldowns(self):
		center = self.mod.build_closing_center(
			workplace="SEOUL-01",
			period={"start_date": "2026-05-01", "end_date": "2026-05-31"},
			items=[
				{
					"doctype": "Korea Attendance Closing",
					"name": "ATT-SEOUL-MAY",
					"workplace": "SEOUL-01",
					"status": "Blocked",
					"blockers": ["E-001: unmarked attendance remains before closing"],
					"metrics": {"employees": 12, "unmarked_days": 3},
				},
				{
					"doctype": "Korea Payroll Verification",
					"name": "PAY-SEOUL-MAY",
					"workplace": "SEOUL-01",
					"status": "Ready",
					"metrics": {"employees": 12, "gross_pay": 48000000},
				},
				{
					"doctype": "Korea Payroll Verification",
					"name": "PAY-BUSAN-MAY",
					"workplace": "BUSAN-01",
					"status": "Blocked",
					"blockers": ["provider consent missing"],
				},
			],
		)

		self.assertEqual(center["workplace"], "SEOUL-01")
		self.assertEqual(center["status"], "Blocked")
		self.assertEqual(center["summary"], {"total_items": 2, "blocked_items": 1, "ready_items": 1, "closed_items": 0})
		self.assertEqual([card["name"] for card in center["cards"]], ["ATT-SEOUL-MAY", "PAY-SEOUL-MAY"])
		self.assertEqual(center["blockers"], [{"source_doctype": "Korea Attendance Closing", "name": "ATT-SEOUL-MAY", "message": "E-001: unmarked attendance remains before closing"}])
		self.assertEqual(center["actions"][0]["action"], "resolve_blockers")
		self.assertFalse(center["actions"][0]["enabled"])
		self.assertEqual(center["actions"][1]["action"], "submit_for_approval")
		self.assertTrue(center["actions"][1]["enabled"])
		self.assertEqual(center["drilldowns"]["Korea Attendance Closing"], ["ATT-SEOUL-MAY"])

	def test_rejects_unknown_status_and_negative_metrics(self):
		with self.assertRaisesRegex(ValueError, "unsupported closing status"):
			self.mod.build_closing_center(
				workplace="SEOUL-01",
				period={"start_date": "2026-05-01", "end_date": "2026-05-31"},
				items=[{"doctype": "Korea Attendance Closing", "name": "ATT-1", "workplace": "SEOUL-01", "status": "Maybe"}],
			)

		with self.assertRaisesRegex(ValueError, "metrics.unmarked_days cannot be negative"):
			self.mod.build_closing_center(
				workplace="SEOUL-01",
				period={"start_date": "2026-05-01", "end_date": "2026-05-31"},
				items=[{"doctype": "Korea Attendance Closing", "name": "ATT-1", "workplace": "SEOUL-01", "status": "Ready", "metrics": {"unmarked_days": -1}}],
			)

	def test_rejects_invalid_period_dates(self):
		for period in (
			{"start_date": "2026-02-30", "end_date": "2026-02-31"},
			{"start_date": "2026-13-01", "end_date": "2026-13-02"},
			{"start_date": "2026-10-01", "end_date": "2026-02-15"},
		):
			with self.subTest(period=period):
				with self.assertRaisesRegex(ValueError, "period"):
					self.mod.build_closing_center(workplace="SEOUL-01", period=period, items=[])

	def test_rejects_non_list_blockers(self):
		with self.assertRaisesRegex(TypeError, "blockers must be a list"):
			self.mod.build_closing_center(
				workplace="SEOUL-01",
				period={"start_date": "2026-05-01", "end_date": "2026-05-31"},
				items=[{"doctype": "Korea Attendance Closing", "name": "ATT-1", "workplace": "SEOUL-01", "status": "Blocked", "blockers": "oops"}],
			)

	def test_ready_to_close_only_when_all_items_ready_or_closed(self):
		center = self.mod.build_closing_center(
			workplace="SEOUL-01",
			period={"start_date": "2026-05-01", "end_date": "2026-05-31"},
			items=[
				{"doctype": "Korea Attendance Closing", "name": "ATT-1", "workplace": "SEOUL-01", "status": "Closed"},
				{"doctype": "Korea Payroll Verification", "name": "PAY-1", "workplace": "SEOUL-01", "status": "Ready"},
			],
		)

		self.assertEqual(center["status"], "Ready To Close")
		self.assertEqual([action["action"] for action in center["actions"]], ["view_audit_log", "submit_for_approval"])


if __name__ == "__main__":
	unittest.main()
