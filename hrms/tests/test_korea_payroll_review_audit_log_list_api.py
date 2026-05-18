#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import json
import pathlib
import sys
import types
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "payroll_review_audit_log_list_api.py"


def load_module(*, with_frappe: bool = False):
	old_frappe = sys.modules.get("frappe")
	if with_frappe:
		fake_frappe = types.SimpleNamespace()

		def whitelist():
			def decorator(fn):
				fn.is_whitelisted_for_test = True
				return fn

			return decorator

		fake_frappe.whitelist = whitelist
		sys.modules["frappe"] = fake_frappe
	else:
		sys.modules.pop("frappe", None)

	try:
		spec = importlib.util.spec_from_file_location("korea_payroll_review_audit_log_list_api", MODULE_PATH)
		module = importlib.util.module_from_spec(spec)
		assert spec.loader is not None
		spec.loader.exec_module(module)
		return module
	finally:
		if old_frappe is not None:
			sys.modules["frappe"] = old_frappe
		else:
			sys.modules.pop("frappe", None)


def audit_row(**overrides):
	row = {
		"contract_type": "korea_payroll_closing_review_audit_log_runtime_insert_v1",
		"runtime_action": "runtime_review_audit_log_created",
		"requires_runtime_apply": False,
		"mutation_boundary": "audit_log_only_no_submit_no_send_no_provider_call",
		"doctype": "Korea Payroll Closing Review Audit Log",
		"docstatus": 0,
		"name": "KPCRA-0001",
		"draft_name": "KPCD-0001",
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
	}
	row.update(overrides)
	return row


class TestKoreaPayrollReviewAuditLogListApi(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()

	def test_preview_api_builds_route_only_audit_log_list_from_json_payloads(self):
		rows = [
			audit_row(name="KPCRA-0001", workplace="Seoul HQ", created_at="2026-06-01T09:30:00+09:00"),
			audit_row(name="KPCRA-0002", workplace="Busan Branch", action="request_changes", status="draft_changes_requested", created_at="2026-06-01T10:00:00+09:00"),
		]

		result = self.mod.preview_korea_payroll_review_audit_log_list(
			company="Korea Demo Co",
			rows=json.dumps(rows),
			workplaces=json.dumps(["Seoul HQ", "Busan Branch"]),
		)

		self.assertEqual(result["contract_type"], "korea_payroll_review_audit_log_list_preview_v1")
		self.assertEqual(result["audit_log_list_contract_type"], "korea_payroll_review_audit_log_list_v1")
		self.assertEqual(result["runtime_action"], "preview_only")
		self.assertFalse(result["requires_runtime_apply"])
		self.assertTrue(result["requires_human_approval"])
		self.assertEqual(result["ai_role"], "assistant_only")
		self.assertEqual(result["total_count"], 2)
		self.assertEqual([item["name"] for item in result["items"]], ["KPCRA-0002", "KPCRA-0001"])
		self.assertEqual(result["action"]["route"], "korea-payroll-review-audit-logs")
		self.assertFalse(result["action"]["requires_runtime_apply"])
		self.assertEqual(result["items"][0]["route"], "korea-payroll-review-audit-logs/KPCRA-0002")
		self.assertFalse(self._contains_forbidden_numeric_score(result))

	def test_preview_api_filters_workplaces_and_defensive_copies_inputs_and_outputs(self):
		rows = [audit_row(name="KPCRA-0001", workplace="Seoul HQ"), audit_row(name="KPCRA-0002", workplace="Busan Branch")]
		workplaces = ["Busan Branch"]
		original = copy.deepcopy({"rows": rows, "workplaces": workplaces})

		result = self.mod.preview_korea_payroll_review_audit_log_list(
			company="Korea Demo Co",
			rows=rows,
			workplaces=workplaces,
		)

		self.assertEqual(result["total_count"], 1)
		self.assertEqual(result["items"][0]["workplace"], "Busan Branch")
		self.assertEqual({"rows": rows, "workplaces": workplaces}, original)
		result["items"][0]["source_audit_log"]["name"] = "MUTATED"
		self.assertEqual(rows[1]["name"], "KPCRA-0002")

	def test_preview_detail_api_builds_route_only_audit_log_detail_from_json_payload(self):
		row = audit_row(name="AUDIT LOG/서울 1")
		row["audit_event"] = {"action": "approve_draft", "status": "draft_human_approved"}
		row["source_runtime_apply"] = {"action": "approve_draft", "status": "draft_human_approved"}

		result = self.mod.preview_korea_payroll_review_audit_log_detail(
			company="Korea Demo Co",
			row=json.dumps(row),
			workplaces=json.dumps(["Seoul HQ"]),
		)

		self.assertEqual(result["contract_type"], "korea_payroll_review_audit_log_detail_preview_v1")
		self.assertEqual(result["audit_log_detail_contract_type"], "korea_payroll_review_audit_log_detail_v1")
		self.assertEqual(result["runtime_action"], "preview_only")
		self.assertFalse(result["requires_runtime_apply"])
		self.assertEqual(result["route"], "korea-payroll-review-audit-logs/AUDIT%20LOG%2F%EC%84%9C%EC%9A%B8%201")
		self.assertEqual(result["audit_event"], {"action": "approve_draft", "status": "draft_human_approved"})
		self.assertEqual(result["source_runtime_apply"], {"action": "approve_draft", "status": "draft_human_approved"})
		self.assertTrue(result["requires_human_approval"])
		self.assertEqual(result["ai_role"], "assistant_only")
		self.assertFalse(self._contains_forbidden_numeric_score(result))

	def test_preview_detail_api_rejects_invalid_row_payloads_and_cross_scope(self):
		with self.assertRaisesRegex(ValueError, "JSON payload is invalid"):
			self.mod.preview_korea_payroll_review_audit_log_detail(company="Korea Demo Co", row='{"bad":', workplaces=None)

		with self.assertRaisesRegex(ValueError, "row must be a JSON object"):
			self.mod.preview_korea_payroll_review_audit_log_detail(company="Korea Demo Co", row="[]", workplaces=None)

		with self.assertRaisesRegex(ValueError, "audit row workplace is outside requested workplaces"):
			self.mod.preview_korea_payroll_review_audit_log_detail(
				company="Korea Demo Co",
				row=audit_row(workplace="Busan Branch"),
				workplaces=["Seoul HQ"],
			)

	def test_preview_api_rejects_invalid_payloads_before_delegation(self):
		with self.assertRaisesRegex(ValueError, "JSON payload is invalid"):
			self.mod.preview_korea_payroll_review_audit_log_list(company="Korea Demo Co", rows='[{"bad":', workplaces=None)

		with self.assertRaisesRegex(ValueError, "rows must be a list or JSON array"):
			self.mod.preview_korea_payroll_review_audit_log_list(company="Korea Demo Co", rows='{"not":"a-list"}', workplaces=None)

		with self.assertRaisesRegex(ValueError, "workplaces must be a list or JSON array"):
			self.mod.preview_korea_payroll_review_audit_log_list(company="Korea Demo Co", rows=[], workplaces='{"not":"a-list"}')

	def test_preview_api_is_whitelisted_when_frappe_is_available(self):
		module = load_module(with_frappe=True)
		self.assertTrue(module.preview_korea_payroll_review_audit_log_list.is_whitelisted_for_test)
		self.assertTrue(module.preview_korea_payroll_review_audit_log_detail.is_whitelisted_for_test)
		self.assertIn("preview_korea_payroll_review_audit_log_detail", module.__all__)

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
