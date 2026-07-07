#!/usr/bin/env python3
from __future__ import annotations

import copy
import datetime as dt
import importlib.util
import json
import pathlib
import sys
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "payroll_closing_worklist_runtime_api.py"


def source_session(**overrides):
	payload = {
		"contract_type": "korea_payroll_closing_session_v1",
		"name": "KPCS-2026-05-SEOUL-HQ",
		"company": "Korea Demo Co",
		"workplace": "Seoul HQ",
		"period_start": "2026-05-01",
		"period_end": "2026-05-31",
		"status": "blocked",
		"blockers": [{"code": "attendance_not_ready", "message": "Attendance is not closed"}],
		"next_actions": [{"action": "resolve_attendance_blockers", "label": "Resolve attendance blockers"}],
		"readiness_cards": [{"key": "attendance", "label": "Attendance", "state": "blocked", "summary": "1 open day"}],
		"payroll_artifacts": {"payroll_entry": "PAY-ENTRY-2026-05", "salary_slip_count": 22},
		"audit_preview": {"runtime_action": "preview_only", "requires_runtime_apply": False, "blocker_codes": ["attendance_not_ready"]},
		"requires_human_approval": True,
		"ai_role": "assistant_only",
	}
	payload.update(overrides)
	return payload


def draft_row(**overrides):
	session = overrides.pop("session", source_session())
	row = {
		"name": "KPCD-2026-05-SEOUL-HQ",
		"company": "Korea Demo Co",
		"workplace": "Seoul HQ",
		"period_start": dt.date(2026, 5, 1),
		"period_end": dt.date(2026, 5, 31),
		"status": "draft_pending_human_approval",
		"source_payroll_entry": "PAY-ENTRY-2026-05",
		"source_session_contract_type": "korea_payroll_closing_session_v1",
		"mutation_boundary": "draft_only_no_submit_no_approve_no_send",
		"requires_human_approval": 1,
		"ai_role": "assistant_only",
		"docstatus": 0,
		"payload": json.dumps({"session": session}, ensure_ascii=False),
		"audit_preview": json.dumps(session.get("audit_preview"), ensure_ascii=False) if "audit_preview" in session else None,
	}
	row.update(overrides)
	return row


class FakeFrappe:
	def __init__(self, rows, *, permissions=None):
		self.rows = [copy.deepcopy(row) for row in rows]
		self.get_list_calls = []
		self.only_for_calls = []
		self.permissions = permissions or {"Korea Payroll Closing Draft": True}
		self.whitelisted = []

	def whitelist(self):
		def decorator(fn):
			fn.is_whitelisted_for_test = True
			self.whitelisted.append(fn.__name__)
			return fn

		return decorator

	def only_for(self, roles):
		self.only_for_calls.append(list(roles))

	def has_permission(self, doctype, ptype="read"):
		return self.permissions.get(doctype, False)

	def get_list(self, doctype, *, filters=None, fields=None, order_by=None, limit_page_length=None):
		self.get_list_calls.append(
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
			if filters and row.get("docstatus") != filters.get("docstatus"):
				continue
			if filters and row.get("status") != filters.get("status"):
				continue
			workplace_filter = (filters or {}).get("workplace")
			if isinstance(workplace_filter, tuple) and workplace_filter[0] == "in" and row.get("workplace") not in workplace_filter[1]:
				continue
			results.append({field: copy.deepcopy(row.get(field)) for field in fields or []})
		return results[:limit_page_length]


class NoPermissionApiFrappe:
	def __init__(self, rows):
		self.rows = rows
		self.get_list_calls = []
		self.whitelisted = []

	def whitelist(self):
		def decorator(fn):
			self.whitelisted.append(fn.__name__)
			return fn

		return decorator

	def get_list(self, *args, **kwargs):
		self.get_list_calls.append((args, kwargs))
		return self.rows


def load_module(fake_frappe):
	old_frappe = sys.modules.get("frappe")
	sys.modules["frappe"] = fake_frappe
	try:
		spec = importlib.util.spec_from_file_location("korea_payroll_closing_worklist_runtime_api", MODULE_PATH)
		module = importlib.util.module_from_spec(spec)
		assert spec.loader is not None
		spec.loader.exec_module(module)
		return module
	finally:
		if old_frappe is not None:
			sys.modules["frappe"] = old_frappe
		else:
			sys.modules.pop("frappe", None)


class TestKoreaPayrollClosingWorklistRuntimeApi(unittest.TestCase):
	def test_runtime_worklist_queries_draft_rows_and_returns_read_only_items(self):
		rows = [
			draft_row(),
			draft_row(
				name="KPCD-2026-05-BUSAN",
				workplace="Busan Branch",
				session=source_session(
					name="KPCS-2026-05-BUSAN",
					workplace="Busan Branch",
					status="review_ready",
					blockers=[],
					payroll_artifacts={"payroll_entry": "PAY-ENTRY-BUSAN-2026-05", "salary_slip_count": 14},
					audit_preview={"runtime_action": "preview_only", "requires_runtime_apply": False, "blocker_codes": []},
				),
			),
		]
		fake_frappe = FakeFrappe(rows)
		module = load_module(fake_frappe)

		result = module.list_korea_payroll_closing_worklist_runtime(
			company="Korea Demo Co",
			workplaces=json.dumps(["Seoul HQ", "Busan Branch"]),
			limit=20,
		)

		self.assertEqual(result["contract_type"], "korea_payroll_closing_worklist_runtime_api_v1")
		self.assertEqual(result["worklist_contract_type"], "korea_payroll_closing_worklist_v1")
		self.assertEqual(result["runtime_action"], "runtime_read_only")
		self.assertFalse(result["requires_runtime_apply"])
		self.assertTrue(result["requires_human_approval"])
		self.assertEqual(result["ai_role"], "assistant_only")
		self.assertEqual(result["summary"]["total_count"], 2)
		self.assertEqual(result["items"][0]["name"], "KPCS-2026-05-SEOUL-HQ")
		self.assertEqual(result["items"][0]["runtime_source_doctype"], "Korea Payroll Closing Draft")
		self.assertEqual(result["items"][0]["draft_name"], "KPCD-2026-05-SEOUL-HQ")
		self.assertEqual(result["items"][0]["readiness_cards"][0]["key"], "attendance")
		self.assertEqual(result["items"][0]["employee_count"], 22)
		self.assertEqual(result["items"][0]["source_session"], {"contract_type": "korea_payroll_closing_session_v1", "name": "KPCS-2026-05-SEOUL-HQ"})
		self.assertEqual(result["items"][0]["runtime_action"], "runtime_read_only")
		self.assertFalse(result["items"][0]["requires_runtime_apply"])
		self.assertEqual(fake_frappe.only_for_calls, [["HR Manager"]])
		self.assertEqual(fake_frappe.get_list_calls[0]["doctype"], "Korea Payroll Closing Draft")
		self.assertEqual(
			fake_frappe.get_list_calls[0]["filters"],
			{"company": "Korea Demo Co", "docstatus": 0, "status": "draft_pending_human_approval", "workplace": ("in", ["Seoul HQ", "Busan Branch"])},
		)
		self.assertEqual(fake_frappe.get_list_calls[0]["limit_page_length"], 20)
		self.assertIn("list_korea_payroll_closing_worklist_runtime", fake_frappe.whitelisted)

	def test_runtime_worklist_hydrates_missing_session_safety_fields_from_draft_row(self):
		session = source_session()
		del session["requires_human_approval"]
		del session["ai_role"]
		module = load_module(FakeFrappe([draft_row(session=session)]))

		result = module.list_korea_payroll_closing_worklist_runtime(company="Korea Demo Co")

		self.assertEqual(result["summary"]["total_count"], 1)
		self.assertTrue(result["requires_human_approval"])
		self.assertEqual(result["ai_role"], "assistant_only")
		self.assertEqual(result["items"][0]["source_session"], {"contract_type": "korea_payroll_closing_session_v1", "name": "KPCS-2026-05-SEOUL-HQ"})

	def test_runtime_worklist_hydrates_legacy_draft_session_status_to_review_ready(self):
		session = source_session(status="draft", blockers=[], next_actions=[], readiness_cards=[], audit_preview={"runtime_action": "preview_only", "requires_runtime_apply": False, "blocker_codes": []})
		del session["blockers"]
		del session["next_actions"]
		del session["audit_preview"]
		module = load_module(FakeFrappe([draft_row(session=session, audit_preview=None)]))

		result = module.list_korea_payroll_closing_worklist_runtime(company="Korea Demo Co")

		self.assertEqual(result["summary"]["review_ready_count"], 1)
		self.assertEqual(result["items"][0]["status"], "review_ready")
		self.assertEqual(result["items"][0]["primary_action"], {"action": "review_payroll_artifacts", "label": "Review payroll artifacts", "requires_runtime_apply": False})
		self.assertEqual(result["items"][0]["audit_preview"], {"runtime_action": "preview_only", "requires_runtime_apply": False, "blocker_codes": []})
		self.assertEqual(result["items"][0]["draft_status"], "draft_pending_human_approval")

	def test_runtime_worklist_queries_only_pending_human_approval_drafts(self):
		rows = [
			draft_row(name="KPCD-2026-05-PENDING"),
			draft_row(name="KPCD-2026-05-APPROVED", status="draft_human_approved"),
			draft_row(name="KPCD-2026-05-REJECTED", status="draft_human_rejected"),
		]
		fake_frappe = FakeFrappe(rows)
		module = load_module(fake_frappe)

		result = module.list_korea_payroll_closing_worklist_runtime(company="Korea Demo Co")

		self.assertEqual(result["summary"]["total_count"], 1)
		self.assertEqual(result["items"][0]["draft_name"], "KPCD-2026-05-PENDING")
		self.assertEqual(fake_frappe.get_list_calls[0]["filters"]["status"], "draft_pending_human_approval")

	def test_runtime_worklist_requires_draft_read_permission_before_querying_rows(self):
		fake_frappe = FakeFrappe([draft_row()], permissions={"Korea Payroll Closing Draft": False})
		module = load_module(fake_frappe)
		with self.assertRaisesRegex(PermissionError, "read permission is required for Korea Payroll Closing Draft"):
			module.list_korea_payroll_closing_worklist_runtime(company="Korea Demo Co")
		self.assertEqual(fake_frappe.get_list_calls, [])

	def test_runtime_worklist_fails_closed_when_permission_apis_are_missing(self):
		fake_frappe = NoPermissionApiFrappe([draft_row()])
		module = load_module(fake_frappe)
		with self.assertRaisesRegex(RuntimeError, "Frappe role and permission APIs are required"):
			module.list_korea_payroll_closing_worklist_runtime(company="Korea Demo Co")
		self.assertEqual(fake_frappe.get_list_calls, [])

	def test_runtime_worklist_does_not_echo_unknown_source_session_fields(self):
		session = source_session(employee_identifier="EMP-SECRET", salary_amount=1234567)
		module = load_module(FakeFrappe([draft_row(session=session)]))
		result = module.list_korea_payroll_closing_worklist_runtime(company="Korea Demo Co")
		self.assertNotIn("employee_identifier", result["items"][0]["source_session"])
		self.assertNotIn("salary_amount", result["items"][0]["source_session"])

	def test_runtime_worklist_sanitizes_readiness_and_audit_payloads(self):
		session = source_session(
			readiness_cards=[{"key": "attendance", "label": "Attendance", "state": "blocked", "summary": "1 open day", "employee_identifier": "EMP-SECRET"}],
			audit_preview={"runtime_action": "preview_only", "requires_runtime_apply": False, "blocker_codes": ["attendance_not_ready"], "internal_note": "do not leak"},
		)
		module = load_module(FakeFrappe([draft_row(session=session)]))
		result = module.list_korea_payroll_closing_worklist_runtime(company="Korea Demo Co")
		self.assertEqual(result["items"][0]["readiness_cards"], [{"key": "attendance", "label": "Attendance", "state": "blocked", "summary": "1 open day"}])
		self.assertEqual(result["items"][0]["audit_preview"], {"runtime_action": "preview_only", "requires_runtime_apply": False, "blocker_codes": ["attendance_not_ready"]})

	def test_runtime_worklist_rejects_mutating_audit_preview_and_row_score_leakage(self):
		mutating_session = source_session(audit_preview={"runtime_action": "submit", "requires_runtime_apply": True, "blocker_codes": []})
		module = load_module(FakeFrappe([draft_row(session=mutating_session)]))
		with self.assertRaisesRegex(ValueError, "payload.session.audit_preview must remain preview-only read metadata"):
			module.list_korea_payroll_closing_worklist_runtime(company="Korea Demo Co")

		module = load_module(
			FakeFrappe(
				[
					draft_row(
						audit_preview=json.dumps({"runtime_action": "preview_only", "requires_runtime_apply": False, "riskRating": "high"})
					)
				]
			)
		)
		with self.assertRaisesRegex(ValueError, "score keys are not allowed"):
			module.list_korea_payroll_closing_worklist_runtime(company="Korea Demo Co")

		module = load_module(
			FakeFrappe(
				[
					draft_row(
						audit_preview=json.dumps({"runtime_action": "submit", "requires_runtime_apply": True, "blocker_codes": []})
					)
				]
			)
		)
		with self.assertRaisesRegex(ValueError, "audit_preview must remain preview-only read metadata"):
			module.list_korea_payroll_closing_worklist_runtime(company="Korea Demo Co")

	def test_runtime_worklist_rejects_duplicate_session_names(self):
		rows = [
			draft_row(name="KPCD-2026-05-SEOUL-A"),
			draft_row(name="KPCD-2026-05-SEOUL-B"),
		]
		module = load_module(FakeFrappe(rows))
		with self.assertRaisesRegex(ValueError, "payload.session.name values must be unique"):
			module.list_korea_payroll_closing_worklist_runtime(company="Korea Demo Co")

	def test_runtime_worklist_preserves_zero_salary_slip_count(self):
		session = source_session(payroll_artifacts={"payroll_entry": "PAY-ENTRY-2026-05", "salary_slip_count": 0, "employee_count": 99})
		module = load_module(FakeFrappe([draft_row(session=session)]))
		result = module.list_korea_payroll_closing_worklist_runtime(company="Korea Demo Co")
		self.assertEqual(result["items"][0]["employee_count"], 0)

	def test_runtime_worklist_rejects_bad_limit_payload_and_score_leakage(self):
		module = load_module(FakeFrappe([draft_row()]))
		with self.assertRaisesRegex(ValueError, "limit must be an integer"):
			module.list_korea_payroll_closing_worklist_runtime(company="Korea Demo Co", limit=True)
		with self.assertRaisesRegex(ValueError, "workplaces must be a list or JSON array"):
			module.list_korea_payroll_closing_worklist_runtime(company="Korea Demo Co", workplaces='{"not":"list"}')

		bad_session = source_session(audit_preview={"legal": {"score": 0.9}, "blocker_codes": []})
		bad_module = load_module(FakeFrappe([draft_row(session=bad_session)]))
		with self.assertRaisesRegex(ValueError, "score keys are not allowed"):
			bad_module.list_korea_payroll_closing_worklist_runtime(company="Korea Demo Co")

		bad_session = source_session(audit_preview={"riskRating": "high", "blocker_codes": []})
		bad_module = load_module(FakeFrappe([draft_row(session=bad_session)]))
		with self.assertRaisesRegex(ValueError, "score keys are not allowed"):
			bad_module.list_korea_payroll_closing_worklist_runtime(company="Korea Demo Co")

	def test_runtime_worklist_fails_closed_on_malformed_stored_session(self):
		module = load_module(FakeFrappe([draft_row(payload=json.dumps({"session": []}))]))
		with self.assertRaisesRegex(ValueError, "payload.session must be a JSON object"):
			module.list_korea_payroll_closing_worklist_runtime(company="Korea Demo Co")



class TestDefaultCompanyFallback(unittest.TestCase):
	def test_company_omitted_falls_back_to_global_defaults(self):
		"""company 미지정 시 Global Defaults default_company로 조회한다 (PWA 딥링크 없이 진입)."""
		fake_frappe = FakeFrappe([])
		import types
		fake_frappe.db = types.SimpleNamespace(
			get_single_value=lambda doctype, field: "노호" if (doctype, field) == ("Global Defaults", "default_company") else None
		)
		module = load_module(fake_frappe)
		result = module.list_korea_payroll_closing_worklist_runtime(company=None)
		self.assertEqual(result["company"], "노호")

	def test_company_omitted_without_default_raises(self):
		fake_frappe = FakeFrappe([])
		import types
		fake_frappe.db = types.SimpleNamespace(get_single_value=lambda doctype, field: None)
		module = load_module(fake_frappe)
		with self.assertRaises(ValueError):
			module.list_korea_payroll_closing_worklist_runtime(company=None)


class TestWorklistRuntimeApproverExposure(unittest.TestCase):
	"""마감 draft의 결재자(approval_state.approver) read-only 노출 — 결재함 0건 혼란 UX."""

	def test_item_exposes_approver_from_session_approval_state(self):
		session = source_session(
			approval_state={
				"company": "Korea Demo Co",
				"workplace": "Seoul HQ",
				"approver": "moon@noho.im",
			}
		)
		module = load_module(FakeFrappe([draft_row(session=session)]))
		result = module.list_korea_payroll_closing_worklist_runtime(company="Korea Demo Co")
		self.assertEqual(result["items"][0]["approver"], "moon@noho.im")

	def test_item_approver_none_when_absent_or_blank(self):
		module = load_module(FakeFrappe([draft_row()]))
		result = module.list_korea_payroll_closing_worklist_runtime(company="Korea Demo Co")
		self.assertIsNone(result["items"][0]["approver"])

		session = source_session(approval_state={"approver": "   "})
		module = load_module(FakeFrappe([draft_row(session=session)]))
		result = module.list_korea_payroll_closing_worklist_runtime(company="Korea Demo Co")
		self.assertIsNone(result["items"][0]["approver"])


if __name__ == "__main__":
	unittest.main()
