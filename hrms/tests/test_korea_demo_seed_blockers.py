#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import types
import unittest
from types import SimpleNamespace

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "demo_seed.py"


def load_module_with_frappe_stub():
	previous_frappe = sys.modules.get("frappe")
	previous_frappe_utils = sys.modules.get("frappe.utils")
	frappe_stub = types.ModuleType("frappe")
	frappe_stub.utils = types.ModuleType("frappe.utils")
	frappe_stub.utils.getdate = lambda value: value
	sys.modules["frappe"] = frappe_stub
	sys.modules["frappe.utils"] = frappe_stub.utils
	try:
		spec = importlib.util.spec_from_file_location("korea_demo_seed", MODULE_PATH)
		module = importlib.util.module_from_spec(spec)
		assert spec.loader is not None
		spec.loader.exec_module(module)
		return module
	finally:
		if previous_frappe is None:
			sys.modules.pop("frappe", None)
		else:
			sys.modules["frappe"] = previous_frappe
		if previous_frappe_utils is None:
			sys.modules.pop("frappe.utils", None)
		else:
			sys.modules["frappe.utils"] = previous_frappe_utils


class TestKoreaDemoSeedBlockerRealism(unittest.TestCase):
	def setUp(self):
		self.mod = load_module_with_frappe_stub()

	def test_demo_blocker_seed_creates_idempotent_unsubmitted_runtime_rows(self):
		calls = []

		def fake_ensure_doc(doctype, name=None, filters=None, values=None):
			calls.append({"doctype": doctype, "name": name, "filters": filters, "values": dict(values or {})})
			return SimpleNamespace(name=name or f"{doctype}-EXISTING"), not any(
				call["doctype"] == doctype and call["name"] == name for call in calls[:-1]
			)

		self.mod.ensure_doc = fake_ensure_doc
		employees = [
			SimpleNamespace(name="HR-EMP-0001", work_location_name="서울 본사"),
			SimpleNamespace(name="HR-EMP-0002", work_location_name="강남 매장"),
		]

		first = self.mod.ensure_demo_blocker_transactions(company="노란봉투법 데모", employees=employees)
		second = self.mod.ensure_demo_blocker_transactions(company="노란봉투법 데모", employees=employees)

		self.assertEqual(first, second)
		self.assertEqual(first["runtime_action"], "demo_seed_only")
		self.assertEqual(first["mutation_boundary"], "demo_seed_idempotent_no_submit_no_approve_no_send_no_provider_call")
		self.assertEqual(first["ai_role"], "assistant_only")
		self.assertFalse(first["requires_runtime_apply"])
		self.assertEqual(
			{row["doctype"] for row in first["blocker_rows"]},
			{"Attendance", "Overtime Slip", "Expense Claim"},
		)
		self.assertTrue(all(row["docstatus"] == 0 for row in first["blocker_rows"]))
		self.assertTrue(all(row["workplace"] in {"서울 본사", "강남 매장"} for row in first["blocker_rows"]))

		attendance_call = next(call for call in calls if call["doctype"] == "Attendance")
		self.assertEqual(
			attendance_call["filters"],
			{
				"company": "노란봉투법 데모",
				"employee": "HR-EMP-0001",
				"attendance_date": "2026-05-15",
				"docstatus": 0,
			},
		)
		self.assertEqual(attendance_call["values"]["naming_series"], "HR-ATT-.YYYY.-")
		self.assertEqual(attendance_call["values"]["status"], "Absent")
		self.assertEqual(attendance_call["values"]["docstatus"], 0)
		self.assertEqual(attendance_call["values"]["company"], "노란봉투법 데모")

		overtime_call = next(call for call in calls if call["doctype"] == "Overtime Slip")
		self.assertEqual(overtime_call["values"]["posting_date"], "2026-05-31")
		self.assertEqual(
			overtime_call["filters"],
			{
				"company": "노란봉투법 데모",
				"employee": "HR-EMP-0002",
				"posting_date": "2026-05-31",
				"start_date": "2026-05-01",
				"end_date": "2026-05-31",
				"docstatus": 0,
			},
		)
		self.assertEqual(overtime_call["values"]["start_date"], "2026-05-01")
		self.assertEqual(overtime_call["values"]["end_date"], "2026-05-31")
		self.assertEqual(overtime_call["values"]["total_overtime_duration"], 2.5)
		self.assertEqual(overtime_call["values"]["docstatus"], 0)
		self.assertEqual(
			overtime_call["values"]["overtime_details"],
			[
				{
					"date": "2026-05-22",
					"overtime_type": "KR Demo Overtime Review",
					"overtime_duration": 2.5,
					"standard_working_hours": 8,
				}
			],
		)

		expense_type_call = next(call for call in calls if call["doctype"] == "Expense Claim Type")
		self.assertEqual(
			expense_type_call["values"]["accounts"],
			[
				{
					"company": "노란봉투법 데모",
					"default_account": "Administrative Expenses - NBG",
				}
			],
		)

		expense_call = next(call for call in calls if call["doctype"] == "Expense Claim")
		self.assertEqual(
			expense_call["filters"],
			{
				"company": "노란봉투법 데모",
				"employee": "HR-EMP-0002",
				"posting_date": "2026-05-28",
				"approval_status": "Draft",
				"docstatus": 0,
			},
		)
		self.assertEqual(expense_call["values"]["naming_series"], "HR-EXP-.YYYY.-")
		self.assertEqual(expense_call["values"]["approval_status"], "Draft")
		self.assertEqual(expense_call["values"]["currency"], "KRW")
		self.assertEqual(expense_call["values"]["exchange_rate"], 1)
		self.assertEqual(expense_call["values"]["docstatus"], 0)
		self.assertEqual(expense_call["values"]["total_claimed_amount"], 86000)
		self.assertEqual(
			expense_call["values"]["expenses"],
			[
				{
					"expense_date": "2026-05-27",
					"expense_type": "KR Demo Meal Transport",
					"description": "Payroll-close demo unsettled meal and transport claim",
					"amount": 86000,
					"sanctioned_amount": 0,
				}
			],
		)

	def test_demo_blocker_seed_rejects_missing_employee_context(self):
		with self.assertRaisesRegex(ValueError, "at least two demo employees"):
			self.mod.ensure_demo_blocker_transactions(company="노란봉투법 데모", employees=[])

		with self.assertRaisesRegex(ValueError, "employee.name must be a non-empty string"):
			self.mod.ensure_demo_blocker_transactions(
				company="노란봉투법 데모",
				employees=[SimpleNamespace(name="", work_location_name="서울 본사"), SimpleNamespace(name="HR-EMP-0002")],
			)

	def test_demo_seed_creates_positive_payroll_closing_draft_row_for_runtime_worklist(self):
		calls = []

		def fake_ensure_doc(doctype, name=None, filters=None, values=None, ignore_links=False, update_existing=True):
			calls.append(
				{
					"doctype": doctype,
					"name": name,
					"filters": filters,
					"values": dict(values or {}),
					"ignore_links": ignore_links,
					"update_existing": update_existing,
				}
			)
			return SimpleNamespace(name=name or f"{doctype}-EXISTING"), True

		self.mod.ensure_doc = fake_ensure_doc
		result = self.mod.ensure_demo_payroll_closing_draft(company="노란봉투법 데모")

		self.assertEqual(result["contract_type"], "korea_demo_payroll_closing_draft_seed_v1")
		self.assertEqual(result["runtime_action"], "demo_seed_only")
		self.assertEqual(result["mutation_boundary"], "demo_seed_idempotent_draft_only_no_submit_no_approve_no_send_no_provider_call")
		self.assertFalse(result["requires_runtime_apply"])
		self.assertTrue(result["requires_human_approval"])
		self.assertEqual(result["ai_role"], "assistant_only")
		self.assertEqual(result["draft_rows"][0]["doctype"], "Korea Payroll Closing Draft")
		self.assertEqual(result["draft_rows"][0]["status"], "draft_pending_human_approval")
		self.assertEqual(result["draft_rows"][0]["docstatus"], 0)

		draft_call = next(call for call in calls if call["doctype"] == "Korea Payroll Closing Draft")
		self.assertTrue(draft_call["ignore_links"])
		self.assertFalse(draft_call["update_existing"])
		self.assertEqual(
			draft_call["filters"],
			{
				"company": "노란봉투법 데모",
				"workplace": "서울 본사",
				"period_start": "2026-05-01",
				"period_end": "2026-05-31",
				"status": "draft_pending_human_approval",
				"docstatus": 0,
			},
		)
		self.assertEqual(draft_call["name"], "KPCD-DEMO-2026-05-SEOUL-HQ")
		self.assertEqual(draft_call["values"]["company"], "노란봉투법 데모")
		self.assertEqual(draft_call["values"]["workplace"], "서울 본사")
		self.assertEqual(draft_call["values"]["period_start"], "2026-05-01")
		self.assertEqual(draft_call["values"]["period_end"], "2026-05-31")
		self.assertEqual(draft_call["values"]["source_session_contract_type"], "korea_payroll_closing_session_v1")
		self.assertEqual(draft_call["values"]["mutation_boundary"], "draft_only_no_submit_no_approve_no_send")
		self.assertTrue(draft_call["values"]["requires_human_approval"])
		self.assertEqual(draft_call["values"]["ai_role"], "assistant_only")

		payload = json.loads(draft_call["values"]["payload"])
		session = payload["session"]
		self.assertEqual(session["contract_type"], "korea_payroll_closing_session_v1")
		self.assertEqual(session["status"], "blocked")
		self.assertEqual(session["company"], "노란봉투법 데모")
		self.assertEqual(session["workplace"], "서울 본사")
		self.assertEqual(session["payroll_artifacts"]["salary_slip_count"], 2)
		self.assertEqual(session["audit_preview"]["runtime_action"], "preview_only")
		self.assertFalse(session["audit_preview"]["requires_runtime_apply"])
		for forbidden in ("score", "risk", "probability", "success_rate", "success rate"):
			self.assertNotIn(forbidden, json.dumps(payload, ensure_ascii=False).lower())

		audit_preview = json.loads(draft_call["values"]["audit_preview"])
		self.assertEqual(audit_preview["runtime_action"], "preview_only")
		self.assertFalse(audit_preview["requires_runtime_apply"])

	def test_demo_payroll_closing_draft_seed_rejects_blank_company(self):
		with self.assertRaisesRegex(ValueError, "company must be a non-empty string"):
			self.mod.ensure_demo_payroll_closing_draft(company=" ")

	def test_demo_browser_credential_handoff_is_report_safe_and_secret_free(self):
		handoff = self.mod.build_demo_browser_credential_handoff()

		self.assertEqual(handoff["contract_type"], "korea_demo_browser_credential_handoff_v1")
		self.assertEqual(handoff["runtime_action"], "demo_credential_handoff_only")
		self.assertFalse(handoff["requires_runtime_apply"])
		self.assertEqual(handoff["username"], "demo.hr.manager@node.pe.kr")
		self.assertEqual(handoff["employee_link_required"], True)
		self.assertEqual(handoff["password_env_var"], "FRAPPE_BROWSER_PASSWORD")
		self.assertNotIn("runtime-secret", json.dumps(handoff).lower())
		self.assertEqual(handoff["mutation_boundary"], "credential_handoff_only_no_payroll_submit_approve_send_provider_call")
		self.assertTrue(handoff["requires_human_approval"])
		self.assertEqual(handoff["ai_role"], "assistant_only")

	def test_demo_browser_credential_runtime_apply_sets_password_without_reporting_secret(self):
		calls = []

		class FakeDB:
			def exists(self, doctype, lookup):
				calls.append(("exists", doctype, lookup))
				if doctype == "User" and lookup == "demo.hr.manager@node.pe.kr":
					return True
				if doctype == "Employee" and lookup == {"user_id": "demo.hr.manager@node.pe.kr", "status": "Active"}:
					return True
				return False

		def fake_update_password(username, password):
			calls.append(("update_password", username, password))

		self.mod.frappe = SimpleNamespace(db=FakeDB())
		self.mod.update_password = fake_update_password

		result = self.mod.ensure_demo_browser_credential(password="runtime-secret-not-reported")

		self.assertEqual(result["contract_type"], "korea_demo_browser_credential_runtime_apply_v1")
		self.assertEqual(result["runtime_action"], "demo_credential_runtime_apply")
		self.assertEqual(result["username"], "demo.hr.manager@node.pe.kr")
		self.assertEqual(result["employee_link_verified"], True)
		self.assertEqual(result["credential_ready_for_browser_verifier"], True)
		self.assertEqual(result["mutation_boundary"], "credential_only_no_payroll_submit_approve_send_provider_call")
		self.assertTrue(result["requires_human_approval"])
		self.assertEqual(result["ai_role"], "assistant_only")
		self.assertNotIn("runtime-secret-not-reported", json.dumps(result))
		self.assertIn(("update_password", "demo.hr.manager@node.pe.kr", "runtime-secret-not-reported"), calls)

	def test_demo_browser_credential_runtime_apply_rejects_non_demo_username(self):
		calls = []

		class FakeDB:
			def exists(self, doctype, lookup):
				calls.append(("exists", doctype, lookup))
				return True

		def fake_update_password(username, password):
			calls.append(("update_password", username, password))

		self.mod.frappe = SimpleNamespace(db=FakeDB())
		self.mod.update_password = fake_update_password

		with self.assertRaisesRegex(ValueError, "username must be the approved demo browser user"):
			self.mod.ensure_demo_browser_credential(username="other.employee@example.com", password="runtime-secret")

		self.assertNotIn(("update_password", "other.employee@example.com", "runtime-secret"), calls)

	def test_demo_browser_credential_runtime_apply_fails_closed_without_active_employee(self):
		class FakeDB:
			def exists(self, doctype, lookup):
				return doctype == "User" and lookup == "demo.hr.manager@node.pe.kr"

		self.mod.frappe = SimpleNamespace(db=FakeDB())

		with self.assertRaisesRegex(ValueError, "active employee linked to demo.hr.manager@node.pe.kr is required"):
			self.mod.ensure_demo_browser_credential(password="runtime-secret")

	def test_ensure_doc_with_filters_does_not_mutate_name_collision_that_fails_scope(self):
		calls = []

		class FakeDB:
			def exists(self, doctype, lookup):
				calls.append(("exists", doctype, lookup))
				if lookup == {"company": "Demo", "docstatus": 0}:
					return False
				if lookup == "KR-DEMO-ROW":
					return True
				return False

		class FakeDoc:
			name = "KR-DEMO-ROW"

			def insert(self, **kwargs):
				calls.append(("insert", kwargs))
				return self

		def fake_get_doc(*args):
			calls.append(("get_doc", args))
			return FakeDoc()

		self.mod.frappe = SimpleNamespace(db=FakeDB(), get_doc=fake_get_doc)

		self.mod.ensure_doc(
			"Attendance",
			name="KR-DEMO-ROW",
			filters={"company": "Demo", "docstatus": 0},
			values={"company": "Demo", "docstatus": 0},
		)

		self.assertNotIn(("get_doc", ("Attendance", "KR-DEMO-ROW")), calls)
		created_payload = next(call[1][0] for call in calls if call[0] == "get_doc")
		self.assertEqual(created_payload["doctype"], "Attendance")
		self.assertEqual(created_payload["name"], "KR-DEMO-ROW")
		self.assertEqual(created_payload["company"], "Demo")


if __name__ == "__main__":
	unittest.main()
