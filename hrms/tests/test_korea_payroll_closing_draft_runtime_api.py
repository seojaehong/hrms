#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import json
import pathlib
import sys
import types
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "payroll_closing_draft_runtime_api.py"


def install_frappe_stub(*, inserted_docs=None, existing_duplicate=None, user="hr.manager@example.com", get_doc_calls=None):
	frappe = types.ModuleType("frappe")
	frappe._ = lambda message: message
	frappe.session = types.SimpleNamespace(user=user)
	frappe.whitelist = lambda *args, **kwargs: (lambda fn: fn)

	def throw(message):
		raise ValueError(message)

	frappe.throw = throw

	class FakeDB:
		def __init__(self):
			self.sql_calls = []

		def exists(self, doctype, filters):
			if existing_duplicate:
				return existing_duplicate
			return None

		def sql(self, query, values=None):
			self.sql_calls.append({"query": query, "values": values})
			if "GET_LOCK" in query:
				return [(1,)]
			if "RELEASE_LOCK" in query:
				return [(1,)]
			return []

	frappe.db = FakeDB()

	class FakeDraftDoc:
		def __init__(self, fields):
			self.fields = dict(fields)
			self.name = "KPCD-0001"

		def insert(self):
			inserted_docs.append(self)
			return self

	def get_doc(fields):
		if get_doc_calls is not None:
			get_doc_calls.append(dict(fields))
		return FakeDraftDoc(fields)

	frappe.get_doc = get_doc
	model = types.ModuleType("frappe.model")
	document = types.ModuleType("frappe.model.document")

	class Document:
		pass

	document.Document = Document
	stubbed_names = ["frappe", "frappe.model", "frappe.model.document"]
	previous_modules = {name: sys.modules.get(name) for name in stubbed_names}
	sys.modules["frappe"] = frappe
	sys.modules["frappe.model"] = model
	sys.modules["frappe.model.document"] = document
	return previous_modules, stubbed_names


def restore_modules(previous_modules, stubbed_names):
	for name in stubbed_names:
		if previous_modules[name] is None:
			sys.modules.pop(name, None)
		else:
			sys.modules[name] = previous_modules[name]


def load_module():
	sys.modules.pop("korea_payroll_closing_draft_runtime_api", None)
	spec = importlib.util.spec_from_file_location("korea_payroll_closing_draft_runtime_api", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


def apply_plan_payload():
	payload = {
		"session": {
			"contract_type": "korea_payroll_closing_session_v1",
			"company": "Korea Demo Co",
			"workplace": "Seoul HQ",
			"period_start": "2026-05-01",
			"period_end": "2026-05-31",
			"status": "review_ready",
			"blockers": [],
			"requires_human_approval": True,
			"ai_role": "assistant_only",
		},
		"review_checklist": [
			{"key": "attendance", "checked": True, "requires_human_review": True, "ai_role": "assistant_only"}
		],
		"audit_preview": {
			"event_type": "korea_payroll_closing_session_review_v1",
			"runtime_action": "preview_only",
			"requires_runtime_apply": True,
			"status": "review_ready",
			"blocker_codes": [],
			"company": "Korea Demo Co",
			"workplace": "Seoul HQ",
			"period_start": "2026-05-01",
			"period_end": "2026-05-31",
		},
	}
	return {
		"contract_type": "korea_payroll_closing_draft_apply_plan_v1",
		"source_draft_contract_type": "korea_payroll_closing_draft_v1",
		"runtime_action": "preview_runtime_draft_apply",
		"requires_runtime_apply": True,
		"mutation_boundary": "draft_only_no_submit_no_approve_no_send",
		"would_create_doctype": "Korea Payroll Closing Draft",
		"docstatus": 0,
		"status": "draft_pending_human_approval",
		"company": "Korea Demo Co",
		"workplace": "Seoul HQ",
		"period_start": "2026-05-01",
		"period_end": "2026-05-31",
		"source_payroll_entry": "PAY-ENTRY-2026-05",
		"approver": "hr.manager@example.com",
		"actor": "hr.manager@example.com",
		"requires_human_approval": True,
		"ai_role": "assistant_only",
		"doctype_insert_preview": {
			"doctype": "Korea Payroll Closing Draft",
			"runtime_action": "preview_only",
			"requires_runtime_apply": True,
			"mutation_boundary": "draft_only_no_submit_no_approve_no_send",
			"fields": {
				"docstatus": 0,
				"company": "Korea Demo Co",
				"workplace": "Seoul HQ",
				"period_start": "2026-05-01",
				"period_end": "2026-05-31",
				"status": "draft_pending_human_approval",
				"source_payroll_entry": "PAY-ENTRY-2026-05",
				"approver": "hr.manager@example.com",
				"source_session_contract_type": "korea_payroll_closing_session_v1",
				"mutation_boundary": "draft_only_no_submit_no_approve_no_send",
				"requires_human_approval": 1,
				"ai_role": "assistant_only",
				"payload": json.dumps(payload, ensure_ascii=False, sort_keys=True),
				"audit_preview": json.dumps(payload["audit_preview"], ensure_ascii=False, sort_keys=True),
			},
		},
	}


class TestKoreaPayrollClosingDraftRuntimeApi(unittest.TestCase):
	def test_runtime_api_inserts_reviewed_draft_from_json_apply_plan(self):
		inserted_docs = []
		previous, names = install_frappe_stub(inserted_docs=inserted_docs)
		try:
			mod = load_module()
			plan = apply_plan_payload()

			result = mod.create_korea_payroll_closing_draft_runtime(apply_plan=json.dumps(plan), actor="hr.manager@example.com")

			self.assertEqual(len(inserted_docs), 1)
			self.assertEqual(result["contract_type"], "korea_payroll_closing_draft_runtime_insert_api_v1")
			self.assertEqual(result["runtime_insert_contract_type"], "korea_payroll_closing_draft_runtime_insert_v1")
			self.assertEqual(result["runtime_action"], "runtime_draft_created")
			self.assertFalse(result["requires_runtime_apply"])
			self.assertEqual(result["mutation_boundary"], "draft_only_no_submit_no_approve_no_send")
			self.assertEqual(result["name"], "KPCD-0001")
			self.assertTrue(result["requires_human_approval"])
			self.assertEqual(result["ai_role"], "assistant_only")
			self.assertFalse(result.get("submitted", False))
			self.assertFalse(result.get("approved", False))
			self.assertFalse(result.get("sent", False))
			self.assertFalse(result.get("provider_called", False))
			lock_queries = [call["query"] for call in sys.modules["frappe"].db.sql_calls]
			self.assertTrue(any("GET_LOCK" in query for query in lock_queries))
			self.assertTrue(any("RELEASE_LOCK" in query for query in lock_queries))
		finally:
			restore_modules(previous, names)

	def test_runtime_api_defaults_actor_to_current_frappe_session_user(self):
		inserted_docs = []
		previous, names = install_frappe_stub(inserted_docs=inserted_docs, user="payroll.ops@example.com")
		try:
			mod = load_module()
			plan = apply_plan_payload()
			plan["actor"] = "plan.actor@example.com"

			result = mod.create_korea_payroll_closing_draft_runtime(apply_plan=plan)

			self.assertEqual(result["actor"], "payroll.ops@example.com")
			self.assertEqual(len(inserted_docs), 1)
		finally:
			restore_modules(previous, names)

	def test_runtime_api_does_not_mutate_caller_apply_plan(self):
		inserted_docs = []
		previous, names = install_frappe_stub(inserted_docs=inserted_docs)
		try:
			mod = load_module()
			plan = apply_plan_payload()
			original = copy.deepcopy(plan)

			mod.create_korea_payroll_closing_draft_runtime(apply_plan=plan, actor="hr.manager@example.com")

			self.assertEqual(plan, original)
		finally:
			restore_modules(previous, names)

	def test_invalid_json_and_non_dict_apply_plan_are_rejected_before_runtime_insert(self):
		inserted_docs = []
		previous, names = install_frappe_stub(inserted_docs=inserted_docs)
		try:
			mod = load_module()

			with self.assertRaisesRegex(ValueError, "JSON payload is invalid"):
				mod.create_korea_payroll_closing_draft_runtime(apply_plan='{"contract_type":', actor="hr.manager@example.com")

			with self.assertRaisesRegex(ValueError, "apply_plan must be a dict or JSON object"):
				mod.create_korea_payroll_closing_draft_runtime(apply_plan="[]", actor="hr.manager@example.com")

			self.assertEqual(inserted_docs, [])
		finally:
			restore_modules(previous, names)

	def test_runtime_api_rejects_preview_wrapper_instead_of_core_apply_plan(self):
		inserted_docs = []
		previous, names = install_frappe_stub(inserted_docs=inserted_docs)
		try:
			mod = load_module()
			plan = apply_plan_payload()
			plan["contract_type"] = "korea_payroll_closing_draft_apply_plan_preview_v1"

			with self.assertRaisesRegex(ValueError, "apply_plan.contract_type must be korea_payroll_closing_draft_apply_plan_v1"):
				mod.create_korea_payroll_closing_draft_runtime(apply_plan=plan, actor="hr.manager@example.com")

			self.assertEqual(inserted_docs, [])
		finally:
			restore_modules(previous, names)

	def test_runtime_api_preserves_duplicate_guard_before_insert(self):
		inserted_docs = []
		get_doc_calls = []
		previous, names = install_frappe_stub(
			inserted_docs=inserted_docs,
			existing_duplicate="KPCD-EXISTING",
			get_doc_calls=get_doc_calls,
		)
		try:
			mod = load_module()

			with self.assertRaisesRegex(ValueError, "Korea Payroll Closing Draft already exists for this company/workplace/period"):
				mod.create_korea_payroll_closing_draft_runtime(
					apply_plan=apply_plan_payload(), actor="hr.manager@example.com"
				)

			self.assertEqual(get_doc_calls, [])
			self.assertEqual(inserted_docs, [])
		finally:
			restore_modules(previous, names)

	def test_runtime_api_uses_duplicate_guard_lock_around_insert(self):
		inserted_docs = []
		previous, names = install_frappe_stub(inserted_docs=inserted_docs)
		try:
			mod = load_module()
			mod.create_korea_payroll_closing_draft_runtime(apply_plan=apply_plan_payload(), actor="hr.manager@example.com")

			queries = [call["query"] for call in sys.modules["frappe"].db.sql_calls]
			self.assertTrue(any("GET_LOCK" in query for query in queries))
			self.assertTrue(any("RELEASE_LOCK" in query for query in queries))
			self.assertEqual(len(inserted_docs), 1)
		finally:
			restore_modules(previous, names)


if __name__ == "__main__":
	unittest.main()
