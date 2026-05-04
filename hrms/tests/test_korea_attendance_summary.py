#!/usr/bin/env python3
"""Direct-run tests for South Korea attendance summary and monthly closing helpers."""

from __future__ import annotations

import datetime as dt
import importlib.util
import pathlib
import unittest


MODULE_PATH = (
	pathlib.Path(__file__).resolve().parents[1]
	/ "regional"
	/ "south_korea"
	/ "attendance_summary.py"
)


def load_module():
	spec = importlib.util.spec_from_file_location("korea_attendance_summary", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


class TestKoreaAttendanceClosingPeriod(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()

	def test_cutoff_period_ending_on_current_month_cutoff(self):
		start, end = self.mod.closing_period_for(dt.date(2026, 5, 20), cutoff_day=25)
		self.assertEqual(start, dt.date(2026, 4, 26))
		self.assertEqual(end, dt.date(2026, 5, 25))

	def test_cutoff_period_rolls_forward_after_cutoff(self):
		start, end = self.mod.closing_period_for(dt.date(2026, 5, 26), cutoff_day=25)
		self.assertEqual(start, dt.date(2026, 5, 26))
		self.assertEqual(end, dt.date(2026, 6, 25))

	def test_cutoff_day_clamps_to_short_month_end(self):
		start, end = self.mod.closing_period_for(dt.date(2026, 2, 15), cutoff_day=31)
		self.assertEqual(start, dt.date(2026, 2, 1))
		self.assertEqual(end, dt.date(2026, 2, 28))

	def test_invalid_cutoff_rejected(self):
		with self.assertRaises(ValueError):
			self.mod.closing_period_for(dt.date(2026, 5, 1), cutoff_day=0)


class TestKoreaAttendanceSummary(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()

	def record(self, employee, day, status, **kwargs):
		return self.mod.AttendanceRecord(
			employee=employee,
			attendance_date=dt.date(2026, 5, day),
			status=status,
			**kwargs,
		)

	def test_summarizes_present_absent_leave_and_hours_by_employee(self):
		records = [
			self.record("EMP-001", 1, "Present", working_hours=8, overtime_hours=1.5),
			self.record("EMP-001", 2, "Work From Home", working_hours=7.5, late_entry=True),
			self.record("EMP-001", 3, "Absent", early_exit=True),
			self.record("EMP-001", 4, "On Leave"),
			self.record("EMP-002", 1, "Present", working_hours=8),
		]

		summary = self.mod.summarize_attendance(
			records,
			period_start=dt.date(2026, 5, 1),
			period_end=dt.date(2026, 5, 31),
		)

		self.assertEqual(summary["EMP-001"]["present_days"], 2.0)
		self.assertEqual(summary["EMP-001"]["absent_days"], 1.0)
		self.assertEqual(summary["EMP-001"]["leave_days"], 1.0)
		self.assertEqual(summary["EMP-001"]["working_hours"], 15.5)
		self.assertEqual(summary["EMP-001"]["overtime_hours"], 1.5)
		self.assertEqual(summary["EMP-001"]["late_entries"], 1)
		self.assertEqual(summary["EMP-001"]["early_exits"], 1)
		self.assertEqual(summary["EMP-002"]["present_days"], 1.0)

	def test_half_day_without_half_day_status_blocks_closing(self):
		summary = self.mod.summarize_attendance(
			[self.record("EMP-001", 1, "Half Day", working_hours=4)],
			period_start=dt.date(2026, 5, 1),
			period_end=dt.date(2026, 5, 31),
		)

		self.assertEqual(summary["EMP-001"]["unresolved_half_days"], 1)
		messages = self.mod.validate_summary_closable(
			summary,
			self.mod.ClosingPolicy(attendance_cutoff_day=25, close_on_missing_attendance=True),
		)
		self.assertTrue(any("unresolved half-day" in msg for msg in messages))

	def test_unmarked_days_can_block_closing(self):
		summary = self.mod.summarize_attendance(
			[self.record("EMP-001", 1, "Present", working_hours=8)],
			period_start=dt.date(2026, 5, 1),
			period_end=dt.date(2026, 5, 31),
			unmarked_days_by_employee={"EMP-001": 2.0, "EMP-002": 1.0},
		)

		self.assertEqual(summary["EMP-001"]["unmarked_days"], 2.0)
		self.assertEqual(summary["EMP-002"]["unmarked_days"], 1.0)
		messages = self.mod.validate_summary_closable(
			summary,
			self.mod.ClosingPolicy(attendance_cutoff_day=25, close_on_missing_attendance=True),
		)
		self.assertEqual(len(messages), 2)
		self.assertTrue(any("EMP-001: unmarked attendance" in msg for msg in messages))
		self.assertTrue(any("EMP-002: unmarked attendance" in msg for msg in messages))

	def test_half_day_absent_counts_half_present_half_absent(self):
		summary = self.mod.summarize_attendance(
			[self.record("EMP-001", 1, "Half Day", half_day_status="Absent", working_hours=4)],
			period_start=dt.date(2026, 5, 1),
			period_end=dt.date(2026, 5, 31),
		)

		self.assertEqual(summary["EMP-001"]["present_days"], 0.5)
		self.assertEqual(summary["EMP-001"]["absent_days"], 0.5)

	def test_holiday_work_is_preserved_for_downstream_payroll(self):
		summary = self.mod.summarize_attendance(
			[
				self.record("EMP-001", 5, "Present", holiday=True, working_hours=8),
				self.record("EMP-001", 6, "Present", weekly_off=True, working_hours=6),
			],
			period_start=dt.date(2026, 5, 1),
			period_end=dt.date(2026, 5, 31),
		)

		self.assertEqual(summary["EMP-001"]["holiday_days"], 1)
		self.assertEqual(summary["EMP-001"]["weekly_off_days"], 1)
		self.assertEqual(summary["EMP-001"]["worked_on_holiday_days"], 1)
		self.assertEqual(summary["EMP-001"]["worked_on_weekly_off_days"], 1)

	def test_build_closing_snapshot_is_deterministic(self):
		summary = {
			"EMP-002": {"present_days": 1.0, "working_hours": 8.0},
			"EMP-001": {"present_days": 2.0, "working_hours": 16.0},
		}

		snapshot_a = self.mod.build_closing_snapshot(
			workplace="WP-SEOUL",
			period_start=dt.date(2026, 5, 1),
			period_end=dt.date(2026, 5, 31),
			summary_by_employee=summary,
		)
		snapshot_b = self.mod.build_closing_snapshot(
			workplace="WP-SEOUL",
			period_start=dt.date(2026, 5, 1),
			period_end=dt.date(2026, 5, 31),
			summary_by_employee=dict(reversed(list(summary.items()))),
		)

		self.assertEqual(snapshot_a["summary_hash"], snapshot_b["summary_hash"])
		self.assertEqual(snapshot_a["employees"], ["EMP-001", "EMP-002"])
		self.assertEqual(snapshot_a["status"], "Ready To Close")

	def test_non_finite_hours_are_rejected(self):
		with self.assertRaises(ValueError):
			self.record("EMP-001", 1, "Present", working_hours=float("nan"))
		with self.assertRaises(ValueError):
			self.record("EMP-001", 1, "Present", overtime_hours=float("inf"))


if __name__ == "__main__":
	unittest.main()
