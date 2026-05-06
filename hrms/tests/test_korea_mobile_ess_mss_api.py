#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import types
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "mobile_ess_mss_api.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_mobile_ess_mss_api", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


class TestKoreaMobileEssMssApi(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()
		self.period = {"start_date": "2026-05-01", "end_date": "2026-05-31"}

	def test_previews_employee_home_from_json_records_without_runtime_mutation(self):
		result = self.mod.preview_korea_mobile_employee_home(
			employee="EMP-001",
			period=json.dumps(self.period),
			records=json.dumps(
				[
					{"record_type": "attendance", "employee": "EMP-001", "status": "Checked In", "workplace": "SEOUL-01"},
					{"record_type": "leave_balance", "employee": "EMP-001", "leave_type": "Annual Leave", "remaining_days": 4},
				]
			),
		)

		self.assertEqual(result["contract_type"], "korea_mobile_ess_home_preview_v1")
		self.assertEqual(result["runtime_action"], "preview_only")
		self.assertFalse(result["requires_runtime_apply"])
		self.assertEqual(result["home"]["contract_type"], "korea_mobile_ess_home_v1")
		self.assertEqual(result["home"]["employee"], "EMP-001")
		self.assertEqual(result["home"]["leave_balances"], [{"leave_type": "Annual Leave", "remaining_days": 4}])

	def test_previews_manager_worklist_and_coerces_today_from_iso_string(self):
		result = self.mod.preview_korea_mobile_manager_worklist(
			manager="MGR-001",
			period=self.period,
			workplace="SEOUL-01",
			today="2026-05-10",
			records=[
				{
					"doctype": "Leave Application",
					"name": "LA-1",
					"employee": "EMP-001",
					"manager": "MGR-001",
					"workplace": "SEOUL-01",
					"status": "Pending",
					"posting_date": "2026-05-04",
				}
			],
		)

		self.assertEqual(result["contract_type"], "korea_mobile_mss_worklist_preview_v1")
		self.assertEqual(result["runtime_action"], "preview_only")
		self.assertFalse(result["requires_runtime_apply"])
		self.assertEqual(result["worklist"]["summary"], {"total": 1, "overdue": 1, "by_doctype": {"Leave Application": 1}})

	def test_manager_worklist_overdue_control_accepts_integral_string_and_rejects_ambiguous_values(self):
		result = self.mod.preview_korea_mobile_manager_worklist(
			manager="MGR-001",
			period=self.period,
			workplace="SEOUL-01",
			today="2026-05-10",
			overdue_after_days="6",
			records=[
				{
					"doctype": "Leave Application",
					"name": "LA-1",
					"employee": "EMP-001",
					"manager": "MGR-001",
					"workplace": "SEOUL-01",
					"status": "Pending",
					"posting_date": "2026-05-04",
				}
			],
		)
		self.assertFalse(result["worklist"]["items"][0]["overdue"])

		for invalid_value in (True, False, 2.5, "2.5", "not-a-number"):
			with self.subTest(invalid_value=invalid_value):
				with self.assertRaisesRegex(ValueError, "overdue_after_days must be an integer"):
					self.mod.preview_korea_mobile_manager_worklist(
						manager="MGR-001",
						period=self.period,
						workplace="SEOUL-01",
						today="2026-05-10",
						overdue_after_days=invalid_value,
						records=[],
					)

	def test_preview_wrappers_do_not_let_downstream_helpers_mutate_caller_inputs(self):
		period = {"start_date": "2026-05-01", "end_date": "2026-05-31"}
		records = [{"record_type": "attendance", "employee": "EMP-001", "status": "Checked In", "workplace": "SEOUL-01"}]

		class MutatingMobileHelper:
			@staticmethod
			def build_mobile_employee_home(*, employee, period, records):
				period["start_date"] = "2099-01-01"
				records[0]["status"] = "MUTATED"
				return {"contract_type": "mutating_helper", "employee": employee, "period": period, "records": records}

		self.mod._load_sibling_module = lambda *_args: MutatingMobileHelper

		result = self.mod.preview_korea_mobile_employee_home(employee="EMP-001", period=period, records=records)
		result["home"]["records"][0]["status"] = "RETURN_MUTATED"

		self.assertEqual(period, {"start_date": "2026-05-01", "end_date": "2026-05-31"})
		self.assertEqual(records, [{"record_type": "attendance", "employee": "EMP-001", "status": "Checked In", "workplace": "SEOUL-01"}])

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

		self.assertEqual(
			calls,
			["preview_korea_mobile_employee_home", "preview_korea_mobile_manager_worklist"],
		)
		self.assertTrue(module.preview_korea_mobile_employee_home.is_whitelisted_for_test)
		self.assertTrue(module.preview_korea_mobile_manager_worklist.is_whitelisted_for_test)

	def test_rejects_malformed_json_and_non_list_records(self):
		with self.assertRaisesRegex(ValueError, "JSON payload is invalid"):
			self.mod.preview_korea_mobile_employee_home(employee="EMP-001", period=self.period, records="[")

		with self.assertRaisesRegex(ValueError, "records must be a list or JSON array"):
			self.mod.preview_korea_mobile_manager_worklist(
				manager="MGR-001",
				period=self.period,
				today="2026-05-10",
				records={"not": "a list"},
			)


if __name__ == "__main__":
	unittest.main()
