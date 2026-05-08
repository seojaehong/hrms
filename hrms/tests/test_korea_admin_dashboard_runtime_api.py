#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import json
import pathlib
import sys
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "admin_dashboard_runtime_api.py"


class FakeDB:
	def __init__(self, counts):
		self.counts = dict(counts)
		self.count_calls = []

	def count(self, doctype, filters=None):
		self.count_calls.append({"doctype": doctype, "filters": copy.deepcopy(filters or {})})
		key = (doctype, json.dumps(filters or {}, sort_keys=True, default=str))
		return self.counts.get(key, 0)


class FakeFrappe:
	def __init__(self, counts, *, employees=None, allowed_roles=True, allowed_permissions=True):
		self.db = FakeDB(counts)
		self.employees = list(employees or [])
		self.get_all_calls = []
		self.whitelisted = []
		self.allowed_roles = allowed_roles
		self.allowed_permissions = allowed_permissions
		self.only_for_calls = []
		self.has_permission_calls = []

	def whitelist(self):
		def decorator(fn):
			fn.is_whitelisted_for_test = True
			self.whitelisted.append(fn.__name__)
			return fn

		return decorator

	def only_for(self, roles):
		self.only_for_calls.append(list(roles))
		if not self.allowed_roles:
			raise PermissionError("not permitted")

	def has_permission(self, doctype, ptype="read"):
		self.has_permission_calls.append({"doctype": doctype, "ptype": ptype})
		return self.allowed_permissions

	def get_all(self, doctype, filters=None, pluck=None):
		self.get_all_calls.append({"doctype": doctype, "filters": copy.deepcopy(filters or {}), "pluck": pluck})
		if doctype != "Employee" or pluck != "name":
			raise AssertionError("unexpected get_all call")
		return list(self.employees)


def count_key(doctype, filters):
	return (doctype, json.dumps(filters, sort_keys=True, default=str))


def load_module(fake_frappe):
	old_frappe = sys.modules.get("frappe")
	sys.modules["frappe"] = fake_frappe
	try:
		spec = importlib.util.spec_from_file_location("korea_admin_dashboard_runtime_api", MODULE_PATH)
		module = importlib.util.module_from_spec(spec)
		assert spec.loader is not None
		spec.loader.exec_module(module)
		return module
	finally:
		if old_frappe is not None:
			sys.modules["frappe"] = old_frappe
		else:
			sys.modules.pop("frappe", None)


class TestKoreaAdminDashboardRuntimeApi(unittest.TestCase):
	def test_runtime_dashboard_counts_drafts_and_audit_logs_by_company_and_workplaces(self):
		counts = {
			count_key(
				"Korea Payroll Closing Draft",
				{"company": "Korea Demo Co", "status": "draft_pending_human_approval", "docstatus": 0, "workplace": ("in", ["Seoul HQ", "Busan Branch"])},
			): 3,
			count_key(
				"Korea Payroll Closing Review Audit Log",
				{"company": "Korea Demo Co", "docstatus": 0, "workplace": ("in", ["Seoul HQ", "Busan Branch"])},
			): 5,
			count_key(
				"Salary Slip",
				{"company": "Korea Demo Co", "docstatus": 0, "employee": ("in", ["EMP-0001", "EMP-0002"])},
			): 7,
			count_key(
				"Attendance",
				{"company": "Korea Demo Co", "docstatus": 0, "employee": ("in", ["EMP-0001", "EMP-0002"])},
			): 4,
		}
		fake_frappe = FakeFrappe(counts, employees=["EMP-0001", "EMP-0002"])
		module = load_module(fake_frappe)

		result = module.get_korea_admin_dashboard_runtime(
			company="Korea Demo Co",
			workplaces=json.dumps(["Seoul HQ", "Busan Branch"]),
		)

		self.assertEqual(result["contract_type"], "korea_admin_dashboard_runtime_api_v1")
		self.assertEqual(result["runtime_action"], "runtime_read_only")
		self.assertFalse(result["requires_runtime_apply"])
		self.assertEqual(result["company"], "Korea Demo Co")
		self.assertEqual(result["workplaces"], ["Seoul HQ", "Busan Branch"])
		self.assertEqual(result["metrics"]["blocked_payroll_closings"], 3)
		self.assertEqual(result["metrics"]["payroll_review_audit_logs"], 5)
		self.assertEqual(result["metrics"]["pending_payslips"], 7)
		self.assertEqual(result["metrics"]["unclosed_attendance"], 4)
		cards = {card["key"]: card for card in result["dashboard"]["cards"]}
		self.assertEqual(cards["pending_payslips"]["value"], 7)
		self.assertEqual(cards["pending_payslips"]["action"]["route"], "korea-closing-center")
		self.assertEqual(cards["unclosed_attendance"]["value"], 4)
		self.assertEqual(cards["unclosed_attendance"]["severity"], "danger")
		self.assertEqual(cards["blocked_payroll_closings"]["value"], 3)
		self.assertEqual(cards["blocked_payroll_closings"]["severity"], "danger")
		self.assertEqual(cards["blocked_payroll_closings"]["action"]["route"], "korea-payroll-closing-session")
		self.assertFalse(cards["blocked_payroll_closings"]["action"]["requires_runtime_apply"])
		self.assertEqual(cards["payroll_review_audit_logs"]["value"], 5)
		self.assertEqual(cards["payroll_review_audit_logs"]["action"]["route"], "korea-payroll-review-audit-logs")
		self.assertEqual(len(fake_frappe.db.count_calls), 4)
		self.assertEqual(
			fake_frappe.get_all_calls,
			[
				{
					"doctype": "Employee",
					"filters": {"company": "Korea Demo Co", "work_location_name": ("in", ["Seoul HQ", "Busan Branch"])},
					"pluck": "name",
				}
			],
		)
		self.assertEqual(fake_frappe.only_for_calls, [["HR Manager"]])
		self.assertEqual(
			fake_frappe.has_permission_calls,
			[
				{"doctype": "Korea Payroll Closing Draft", "ptype": "read"},
				{"doctype": "Korea Payroll Closing Review Audit Log", "ptype": "read"},
				{"doctype": "Employee", "ptype": "read"},
				{"doctype": "Salary Slip", "ptype": "read"},
				{"doctype": "Attendance", "ptype": "read"},
			],
		)
		self.assertIn("get_korea_admin_dashboard_runtime", fake_frappe.whitelisted)

	def test_runtime_dashboard_rejects_invalid_scope_before_counting(self):
		fake_frappe = FakeFrappe({})
		module = load_module(fake_frappe)

		with self.assertRaisesRegex(ValueError, "company must be a non-empty string"):
			module.get_korea_admin_dashboard_runtime(company=" ")
		with self.assertRaisesRegex(ValueError, "workplaces must be a list or JSON array"):
			module.get_korea_admin_dashboard_runtime(company="Korea Demo Co", workplaces='{"not":"list"}')
		with self.assertRaisesRegex(ValueError, "workplaces must contain non-empty strings"):
			module.get_korea_admin_dashboard_runtime(company="Korea Demo Co", workplaces=["Seoul HQ", ""])
		self.assertEqual(fake_frappe.db.count_calls, [])

	def test_runtime_dashboard_rejects_unauthorized_roles_and_permissions_before_counting(self):
		role_denied = FakeFrappe({}, allowed_roles=False)
		role_module = load_module(role_denied)
		with self.assertRaises(PermissionError):
			role_module.get_korea_admin_dashboard_runtime(company="Korea Demo Co")
		self.assertEqual(role_denied.db.count_calls, [])

		permission_denied = FakeFrappe({}, allowed_permissions=False)
		permission_module = load_module(permission_denied)
		with self.assertRaisesRegex(PermissionError, "read permission is required"):
			permission_module.get_korea_admin_dashboard_runtime(company="Korea Demo Co")
		self.assertEqual(permission_denied.db.count_calls, [])

	def test_runtime_dashboard_preserves_zero_defaults_without_mutation_or_score_keys(self):
		fake_frappe = FakeFrappe({})
		module = load_module(fake_frappe)

		result = module.get_korea_admin_dashboard_runtime(company="Korea Demo Co")

		self.assertEqual(result["dashboard"]["status"], "Ready")
		self.assertEqual(result["metrics"]["blocked_payroll_closings"], 0)
		self.assertEqual(result["metrics"]["payroll_review_audit_logs"], 0)
		self.assertEqual(result["metrics"]["pending_payslips"], 0)
		self.assertEqual(result["metrics"]["unclosed_attendance"], 0)
		self.assertFalse(self._contains_forbidden_numeric_score(result))

	def _contains_forbidden_numeric_score(self, value):
		forbidden = {"risk_score", "probability", "success_rate", "score"}
		if isinstance(value, dict):
			for key, child in value.items():
				if key in forbidden:
					return True
				if self._contains_forbidden_numeric_score(child):
					return True
		if isinstance(value, list):
			return any(self._contains_forbidden_numeric_score(child) for child in value)
		return False


if __name__ == "__main__":
	unittest.main()
