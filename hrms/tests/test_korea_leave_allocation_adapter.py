#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import importlib.util
import pathlib
import unittest
from types import SimpleNamespace

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "leave_allocation_adapter.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_leave_allocation_adapter", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


class TestKoreaLeaveAllocationAdapter(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()

	def test_builds_leave_allocation_draft_from_employee_profile_and_entitlement(self):
		employee = SimpleNamespace(
			name="EMP-0001",
			employee_name="Kim Mina",
			company="Korea Demo Co",
			date_of_joining="2026-07-01",
		)

		payload = self.mod.build_korea_leave_allocation_draft(
			employee=employee,
			as_of_date=dt.date(2026, 12, 31),
			basis="Fiscal Year",
			leave_type="Annual Leave",
		)

		self.assertEqual(payload["contract_type"], "korea_leave_allocation_draft_v1")
		self.assertEqual(payload["source"], {"doctype": "Employee", "name": "EMP-0001"})
		self.assertEqual(payload["doctype"], "Leave Allocation")
		self.assertEqual(payload["employee"], "EMP-0001")
		self.assertEqual(payload["employee_name"], "Kim Mina")
		self.assertEqual(payload["company"], "Korea Demo Co")
		self.assertEqual(payload["leave_type"], "Annual Leave")
		self.assertEqual(payload["from_date"], "2026-01-01")
		self.assertEqual(payload["to_date"], "2026-12-31")
		self.assertEqual(payload["new_leaves_allocated"], 12.56)
		self.assertEqual(payload["unused_leaves"], 12.56)
		self.assertFalse(payload["carry_forward"])
		self.assertTrue(payload["requires_runtime_apply"])
		self.assertEqual(payload["entitlement_reference"]["basis"], "Fiscal Year")

	def test_caps_allocation_period_and_entitlement_by_employment_end_date(self):
		employee = {
			"name": "EMP-0002",
			"company": "Korea Demo Co",
			"date_of_joining": "2026-07-01",
			"relieving_date": "2026-09-30",
		}

		payload = self.mod.build_korea_leave_allocation_draft(
			employee=employee,
			as_of_date="2026-12-31",
			basis="Fiscal Year",
		)

		self.assertEqual(payload["to_date"], "2026-09-30")
		self.assertEqual(payload["new_leaves_allocated"], 5.78)
		self.assertEqual(payload["entitlement_reference"]["employment_end_date"], "2026-09-30")

	def test_normalizes_datetime_boundaries_and_existing_allocations_for_runtime_inputs(self):
		payload = self.mod.build_korea_leave_allocation_draft(
			employee={"name": "EMP-0003", "date_of_joining": dt.datetime(2026, 3, 1, 9, 30)},
			as_of_date=dt.datetime(2027, 3, 1, 18, 0),
			existing_allocated_days="5",
		)

		self.assertEqual(payload["leave_type"], "Annual Leave")
		self.assertEqual(payload["from_date"], "2027-03-01")
		self.assertEqual(payload["new_leaves_allocated"], 10)
		self.assertEqual(payload["existing_allocated_days"], 5)
		self.assertEqual(payload["entitlement_reference"]["hire_date"], "2026-03-01")
		self.assertEqual(payload["entitlement_reference"]["as_of_date"], "2027-03-01")

	def test_custom_fiscal_year_start_shapes_allocation_period(self):
		payload = self.mod.build_korea_leave_allocation_draft(
			employee={"name": "EMP-0004", "date_of_joining": "2026-07-01"},
			as_of_date="2027-03-15",
			basis="Fiscal Year",
			fiscal_year_start_month=3,
			fiscal_year_start_day=1,
		)

		self.assertEqual(payload["from_date"], "2027-03-01")
		self.assertEqual(payload["to_date"], "2028-02-29")
		self.assertEqual(payload["entitlement_reference"]["basis"], "Fiscal Year")

	def test_rejects_missing_required_employee_fields_and_negative_existing_allocation(self):
		with self.assertRaisesRegex(ValueError, "employee.name is required"):
			self.mod.build_korea_leave_allocation_draft(
				employee={"date_of_joining": "2026-01-01"},
				as_of_date="2026-12-31",
			)

		with self.assertRaisesRegex(ValueError, "employee.date_of_joining is required"):
			self.mod.build_korea_leave_allocation_draft(
				employee={"name": "EMP-0003"},
				as_of_date="2026-12-31",
			)

		with self.assertRaisesRegex(ValueError, "existing_allocated_days cannot be negative"):
			self.mod.build_korea_leave_allocation_draft(
				employee={"name": "EMP-0003", "date_of_joining": "2026-01-01"},
				as_of_date="2026-12-31",
				existing_allocated_days=-1,
			)


if __name__ == "__main__":
	unittest.main()
