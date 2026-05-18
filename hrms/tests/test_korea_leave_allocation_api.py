#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import types
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "leave_allocation_api.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_leave_allocation_api", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


class TestKoreaLeaveAllocationApi(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()

	def test_previews_leave_allocation_draft_from_json_employee_without_runtime_mutation(self):
		employee = {
			"name": "EMP-0001",
			"employee_name": "Kim Mina",
			"company": "Korea Demo Co",
			"date_of_joining": "2026-07-01",
		}

		result = self.mod.preview_korea_leave_allocation_draft(
			employee=json.dumps(employee),
			as_of_date="2026-12-31",
			basis="Fiscal Year",
			existing_allocated_days="2",
		)

		self.assertEqual(result["contract_type"], "korea_leave_allocation_preview_v1")
		self.assertEqual(result["runtime_action"], "preview_only")
		self.assertTrue(result["requires_runtime_apply"])
		self.assertEqual(result["draft"]["contract_type"], "korea_leave_allocation_draft_v1")
		self.assertEqual(result["draft"]["employee"], "EMP-0001")
		self.assertEqual(result["draft"]["new_leaves_allocated"], 10.56)
		self.assertEqual(result["draft"]["existing_allocated_days"], 2)

	def test_preview_does_not_let_downstream_adapter_mutate_caller_input_or_return_reference(self):
		employee = {"name": "EMP-0002", "date_of_joining": "2026-01-01"}

		class MutatingAdapter:
			@staticmethod
			def build_korea_leave_allocation_draft(**kwargs):
				kwargs["employee"]["name"] = "MUTATED"
				return {"contract_type": "mutating_draft", "employee": kwargs["employee"]}

		self.mod._load_sibling_module = lambda *_args: MutatingAdapter

		result = self.mod.preview_korea_leave_allocation_draft(employee=employee, as_of_date="2026-12-31")
		result["draft"]["employee"]["name"] = "RETURN_MUTATED"

		self.assertEqual(employee, {"name": "EMP-0002", "date_of_joining": "2026-01-01"})

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

		self.assertEqual(calls, ["preview_korea_leave_allocation_draft"])
		self.assertTrue(module.preview_korea_leave_allocation_draft.is_whitelisted_for_test)

	def test_rejects_malformed_json_and_non_object_employee_payload(self):
		with self.assertRaisesRegex(ValueError, "JSON payload is invalid"):
			self.mod.preview_korea_leave_allocation_draft(employee="{", as_of_date="2026-12-31")

		with self.assertRaisesRegex(ValueError, "employee must be a dict or JSON object"):
			self.mod.preview_korea_leave_allocation_draft(employee=[], as_of_date="2026-12-31")

	def test_rejects_bool_and_non_integral_fiscal_year_controls(self):
		employee = {"name": "EMP-0003", "date_of_joining": "2026-01-01"}

		with self.assertRaisesRegex(ValueError, "fiscal_year_start_month must be an integer"):
			self.mod.preview_korea_leave_allocation_draft(
				employee=employee,
				as_of_date="2026-12-31",
				basis="Fiscal Year",
				fiscal_year_start_month=True,
			)

		with self.assertRaisesRegex(ValueError, "fiscal_year_start_day must be an integer"):
			self.mod.preview_korea_leave_allocation_draft(
				employee=employee,
				as_of_date="2026-12-31",
				basis="Fiscal Year",
				fiscal_year_start_day=1.5,
			)

if __name__ == "__main__":
	unittest.main()
