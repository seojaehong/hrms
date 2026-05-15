#!/usr/bin/env python3
from __future__ import annotations

import copy
import datetime as dt
import importlib.util
import json
import pathlib
import sys
import types
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "payroll_review_audit_log_runtime_api.py"


def runtime_row(**overrides):
	row = {
		"contract_type": "korea_payroll_closing_review_audit_log_runtime_insert_v1",
		"runtime_action": "runtime_review_audit_log_created",
		"requires_runtime_apply": False,
		"mutation_boundary": "audit_log_only_no_submit_no_send_no_provider_call",
		"doctype": "Korea Payroll Closing Review Audit Log",
		"docstatus": 0,
		"name": "KPCRAL-2026-05-SEOUL-001",
		"draft_name": "KPCD-2026-05-SEOUL-001",
		"previous_status": "draft_pending_human_approval",
		"status": "draft_human_approved",
		"action": "approve_draft",
		"review_actor": "hr.manager@example.com",
		"audit_actor": "hr.auditor@example.com",
		"company": "Korea Demo Co",
		"workplace": "Seoul HQ",
		"period_start": "2026-05-01",
		"period_end": "2026-05-31",
		"source_payroll_entry": "PAY-ENTRY-2026-05",
		"source_audit_log_contract_type": "korea_payroll_closing_draft_review_audit_log_v1",
		"requires_human_approval": True,
		"ai_role": "assistant_only",
		"created_at": "2026-06-01T09:30:00+09:00",
		"audit_event": {"action": "approve_draft", "status": "draft_human_approved"},
		"source_runtime_apply": {"action": "approve_draft", "status": "draft_human_approved"},
	}
	row.update(overrides)
	return row


class FakeDoc:
	def __init__(self, payload):
		for key, value in payload.items():
			setattr(self, key, value)


class FakeFrappe:
	def __init__(self, rows, *, allowed_roles=True, allowed_permissions=True, allowed_companies=None, allowed_workplaces=None):
		self.rows = [copy.deepcopy(row) for row in rows]
		self.get_all_calls = []
		self.get_doc_calls = []
		self.whitelisted = []
		self.allowed_roles = allowed_roles
		self.allowed_permissions = allowed_permissions
		self.allowed_companies = allowed_companies
		self.allowed_workplaces = allowed_workplaces
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

	def get_value(self, doctype, filters, fieldname):
		if doctype == "Employee" and fieldname == "company" and self.allowed_companies is not None:
			return self.allowed_companies[0] if self.allowed_companies else None
		return None

	def get_all(self, doctype, *, filters=None, fields=None, order_by=None, limit_page_length=None):
		self.get_all_calls.append(
			{
				"doctype": doctype,
				"filters": copy.deepcopy(filters),
				"fields": list(fields or []),
				"order_by": order_by,
				"limit_page_length": limit_page_length,
			}
		)
		results = []
		for row in self.rows:
			if filters and row.get("company") != filters.get("company"):
				continue
			if filters and filters.get("name") is not None and row.get("name") != filters.get("name"):
				continue
			workplace_filter = (filters or {}).get("workplace")
			if isinstance(workplace_filter, tuple) and workplace_filter[0] == "in" and row.get("workplace") not in workplace_filter[1]:
				continue
			results.append({field: copy.deepcopy(row.get(field)) for field in fields or []})
		return results[:limit_page_length]

	def get_doc(self, doctype, name):
		self.get_doc_calls.append({"doctype": doctype, "name": name})
		for row in self.rows:
			if row["name"] == name:
				return FakeDoc(copy.deepcopy(row))
		raise ValueError("not found")


def load_module(fake_frappe):
	old_frappe = sys.modules.get("frappe")
	sys.modules["frappe"] = fake_frappe
	try:
		spec = importlib.util.spec_from_file_location("korea_payroll_review_audit_log_runtime_api", MODULE_PATH)
		module = importlib.util.module_from_spec(spec)
		assert spec.loader is not None
		spec.loader.exec_module(module)
		return module
	finally:
		if old_frappe is not None:
			sys.modules["frappe"] = old_frappe
		else:
			sys.modules.pop("frappe", None)


class TestKoreaPayrollReviewAuditLogRuntimeApi(unittest.TestCase):
	def test_runtime_list_queries_doctype_and_returns_preview_only_operator_list(self):
		rows = [
			runtime_row(name="KPCRAL-SEOUL-001", workplace="Seoul HQ", period_start=dt.date(2026, 5, 1), period_end=dt.date(2026, 5, 31), created_at="2026-06-01T09:30:00+09:00", creation=dt.datetime(2026, 6, 1, 9, 30)),
			runtime_row(name="KPCRAL-BUSAN-001", workplace="Busan Branch", action="request_changes", status="draft_changes_requested", created_at="2026-06-01T10:00:00+09:00", creation="2026-06-01 10:00:00.000000"),
		]
		fake_frappe = FakeFrappe(rows)
		module = load_module(fake_frappe)

		result = module.list_korea_payroll_review_audit_logs_runtime(
			company="Korea Demo Co",
			workplaces=json.dumps(["Seoul HQ", "Busan Branch"]),
			limit=20,
		)

		self.assertEqual(result["contract_type"], "korea_payroll_review_audit_log_runtime_list_api_v1")
		self.assertEqual(result["audit_log_list_contract_type"], "korea_payroll_review_audit_log_list_v1")
		self.assertEqual(result["runtime_action"], "runtime_read_only")
		self.assertFalse(result["requires_runtime_apply"])
		self.assertTrue(result["requires_human_approval"])
		self.assertEqual(result["ai_role"], "assistant_only")
		self.assertEqual(result["total_count"], 2)
		self.assertEqual(fake_frappe.get_all_calls[0]["doctype"], "Korea Payroll Closing Review Audit Log")
		self.assertEqual(fake_frappe.get_all_calls[0]["filters"]["workplace"], ("in", ["Seoul HQ", "Busan Branch"]))
		self.assertEqual(fake_frappe.get_all_calls[0]["limit_page_length"], 20)
		self.assertEqual(fake_frappe.only_for_calls, [["HR Manager"]])
		self.assertEqual(
			fake_frappe.has_permission_calls,
			[{"doctype": "Korea Payroll Closing Review Audit Log", "ptype": "read"}],
		)
		self.assertIn("list_korea_payroll_review_audit_logs_runtime", fake_frappe.whitelisted)
		self.assertFalse(self._contains_forbidden_numeric_score(result))

	def test_runtime_detail_queries_one_doctype_row_and_preserves_embedded_payloads(self):
		row = runtime_row(name="KPCRAL/서울 001")
		fake_frappe = FakeFrappe([row])
		module = load_module(fake_frappe)

		result = module.get_korea_payroll_review_audit_log_detail_runtime(
			company="Korea Demo Co",
			name="KPCRAL/서울 001",
			workplaces=json.dumps(["Seoul HQ"]),
		)

		self.assertEqual(result["contract_type"], "korea_payroll_review_audit_log_runtime_detail_api_v1")
		self.assertEqual(result["audit_log_detail_contract_type"], "korea_payroll_review_audit_log_detail_v1")
		self.assertEqual(result["runtime_action"], "runtime_read_only")
		self.assertFalse(result["requires_runtime_apply"])
		self.assertEqual(result["route"], "korea-payroll-review-audit-logs/KPCRAL%2F%EC%84%9C%EC%9A%B8%20001")
		self.assertEqual(result["audit_event"], {"action": "approve_draft", "status": "draft_human_approved"})
		self.assertEqual(result["source_runtime_apply"], {"action": "approve_draft", "status": "draft_human_approved"})
		self.assertEqual(fake_frappe.get_doc_calls, [])
		self.assertEqual(fake_frappe.get_all_calls[0]["filters"]["name"], "KPCRAL/서울 001")
		self.assertEqual(fake_frappe.get_all_calls[0]["filters"]["company"], "Korea Demo Co")
		self.assertEqual(fake_frappe.get_all_calls[0]["filters"]["workplace"], ("in", ["Seoul HQ"]))
		self.assertIn("get_korea_payroll_review_audit_log_detail_runtime", fake_frappe.whitelisted)

	def test_runtime_read_rejects_unauthorized_role_permission_and_scope_before_query(self):
		role_denied = FakeFrappe([runtime_row()], allowed_roles=False)
		role_module = load_module(role_denied)
		with self.assertRaises(PermissionError):
			role_module.list_korea_payroll_review_audit_logs_runtime(company="Korea Demo Co")
		self.assertEqual(role_denied.get_all_calls, [])

		permission_denied = FakeFrappe([runtime_row()], allowed_permissions=False)
		permission_module = load_module(permission_denied)
		with self.assertRaisesRegex(PermissionError, "read permission is required"):
			permission_module.get_korea_payroll_review_audit_log_detail_runtime(
				company="Korea Demo Co",
				name="KPCRAL-2026-05-SEOUL-001",
			)
		self.assertEqual(permission_denied.get_all_calls, [])

		company_denied = FakeFrappe([runtime_row()], allowed_companies=["Other Co"] )
		company_module = load_module(company_denied)
		with self.assertRaisesRegex(PermissionError, "company is outside the current user's allowed scope"):
			company_module.list_korea_payroll_review_audit_logs_runtime(company="Korea Demo Co")
		self.assertEqual(company_denied.get_all_calls, [])

		workplace_denied = FakeFrappe([runtime_row()], allowed_workplaces=["Busan Branch"] )
		workplace_module = load_module(workplace_denied)
		with self.assertRaisesRegex(PermissionError, "workplaces are outside the current user's allowed scope"):
			workplace_module.list_korea_payroll_review_audit_logs_runtime(
				company="Korea Demo Co",
				workplaces=["Seoul HQ"],
			)
		self.assertEqual(workplace_denied.get_all_calls, [])

	def test_runtime_api_rejects_bad_scope_limit_and_score_leakage_before_returning(self):
		fake_frappe = FakeFrappe([runtime_row(audit_event={"legal": {"score": 0.9}})])
		module = load_module(fake_frappe)

		with self.assertRaisesRegex(ValueError, "limit must be an integer"):
			module.list_korea_payroll_review_audit_logs_runtime(company="Korea Demo Co", limit=True)

		with self.assertRaisesRegex(ValueError, "workplaces must be a list or JSON array"):
			module.list_korea_payroll_review_audit_logs_runtime(company="Korea Demo Co", workplaces='{"not":"list"}')

		with self.assertRaisesRegex(ValueError, "score keys are not allowed"):
			module.list_korea_payroll_review_audit_logs_runtime(company="Korea Demo Co")

		clean_module = load_module(FakeFrappe([runtime_row()]))
		with self.assertRaisesRegex(ValueError, "audit row was not found in the requested company/workplace scope"):
			clean_module.get_korea_payroll_review_audit_log_detail_runtime(
				company="Korea Demo Co",
				name="KPCRAL-2026-05-SEOUL-001",
				workplaces=["Busan Branch"],
			)

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
