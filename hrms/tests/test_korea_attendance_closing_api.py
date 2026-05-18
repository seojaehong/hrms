#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import types
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "attendance_closing_api.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_attendance_closing_api", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


class TestKoreaAttendanceClosingApi(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()

	def test_previews_attendance_closing_snapshot_from_json_without_runtime_mutation(self):
		records = [
			{
				"employee": "EMP-001",
				"attendance_date": "2026-05-01",
				"status": "Present",
				"working_hours": 8,
			},
			{
				"employee": "EMP-001",
				"attendance_date": "2026-05-02",
				"status": "Half Day",
				"half_day_status": "Absent",
				"working_hours": 4,
			},
		]
		policy = {
			"attendance_cutoff_day": 25,
			"standard_work_hours_per_day": 8,
			"close_on_missing_attendance": True,
		}
		unmarked = {"EMP-001": 1}

		result = self.mod.preview_korea_attendance_closing(
			workplace="SEOUL-01",
			period_start="2026-05-01",
			period_end="2026-05-31",
			records=json.dumps(records),
			policy=json.dumps(policy),
			unmarked_days_by_employee=json.dumps(unmarked),
		)

		self.assertEqual(result["contract_type"], "korea_attendance_closing_preview_v1")
		self.assertEqual(result["runtime_action"], "preview_only")
		self.assertTrue(result["requires_runtime_apply"])
		snapshot = result["snapshot"]
		self.assertEqual(snapshot["workplace"], "SEOUL-01")
		self.assertEqual(snapshot["period_start"], "2026-05-01")
		self.assertEqual(snapshot["period_end"], "2026-05-31")
		self.assertEqual(snapshot["summary_by_employee"]["EMP-001"]["present_days"], 1.5)
		self.assertEqual(snapshot["summary_by_employee"]["EMP-001"]["unmarked_days"], 1.0)
		self.assertEqual(snapshot["status"], "Blocked")
		self.assertIn("EMP-001: unmarked attendance remains before closing", snapshot["blocking_messages"])

	def test_preview_wrapper_does_not_mutate_caller_inputs_or_return_core_date_objects(self):
		records = [{"employee": "EMP-001", "attendance_date": "2026-05-01", "status": "Present"}]
		policy = {"attendance_cutoff_day": 25}
		unmarked = {"EMP-001": 0}

		result = self.mod.preview_korea_attendance_closing(
			workplace="SEOUL-01",
			period_start="2026-05-01",
			period_end="2026-05-31",
			records=records,
			policy=policy,
			unmarked_days_by_employee=unmarked,
		)
		result["snapshot"]["summary_by_employee"]["EMP-001"]["present_days"] = 99

		self.assertEqual(records, [{"employee": "EMP-001", "attendance_date": "2026-05-01", "status": "Present"}])
		self.assertEqual(policy, {"attendance_cutoff_day": 25})
		self.assertEqual(unmarked, {"EMP-001": 0})
		self.assertEqual(result["snapshot"]["period_start"], "2026-05-01")

	def test_frappe_present_import_applies_whitelist_decorator(self):
		calls = []

		def whitelist():
			def decorator(fn):
				calls.append(fn.__name__)
				fn.is_whitelisted_for_test = True
				return fn

			return decorator

		fake_frappe = types.SimpleNamespace(whitelist=whitelist)
		old_frappe = sys.modules.get("frappe")
		sys.modules["frappe"] = fake_frappe
		try:
			module = load_module()
		finally:
			if old_frappe is None:
				sys.modules.pop("frappe", None)
			else:
				sys.modules["frappe"] = old_frappe

		self.assertEqual(calls, ["preview_korea_attendance_closing"])
		self.assertTrue(module.preview_korea_attendance_closing.is_whitelisted_for_test)

	def test_rejects_malformed_json_and_bad_shapes_before_core_call(self):
		with self.assertRaisesRegex(ValueError, "JSON payload is invalid"):
			self.mod.preview_korea_attendance_closing(
				workplace="SEOUL-01", period_start="2026-05-01", period_end="2026-05-31", records="{", policy={}
			)

		with self.assertRaisesRegex(ValueError, "records must be a list or JSON array"):
			self.mod.preview_korea_attendance_closing(
				workplace="SEOUL-01", period_start="2026-05-01", period_end="2026-05-31", records={}, policy={}
			)

		with self.assertRaisesRegex(ValueError, "policy must be a dict or JSON object"):
			self.mod.preview_korea_attendance_closing(
				workplace="SEOUL-01", period_start="2026-05-01", period_end="2026-05-31", records=[], policy=[]
			)

		with self.assertRaisesRegex(ValueError, "attendance_date is required"):
			self.mod.preview_korea_attendance_closing(
				workplace="SEOUL-01",
				period_start="2026-05-01",
				period_end="2026-05-31",
				records=[{"employee": "EMP-001", "status": "Present"}],
				policy={"attendance_cutoff_day": 25},
			)


if __name__ == "__main__":
	unittest.main()
