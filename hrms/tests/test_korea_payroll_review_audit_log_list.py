#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "payroll_review_audit_log_list.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_payroll_review_audit_log_list", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


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


class TestKoreaPayrollReviewAuditLogList(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()

	def test_builds_operator_audit_log_list_for_company_and_workplaces(self):
		rows = [
			audit_row(name="KPCRA-0001", workplace="Seoul HQ", created_at="2026-06-01T09:30:00+09:00"),
			audit_row(name="KPCRA-0002", workplace="Busan Branch", action="request_changes", status="draft_changes_requested", created_at="2026-06-01T10:00:00+09:00"),
			audit_row(name="KPCRA-OTHER", company="Other Co", workplace="Seoul HQ"),
			audit_row(name="KPCRA-SKIP", workplace="Incheon Branch"),
		]

		view = self.mod.build_korea_payroll_review_audit_log_list(
			rows,
			company="Korea Demo Co",
			workplaces=["Seoul HQ", "Busan Branch"],
		)

		self.assertEqual(view["contract_type"], "korea_payroll_review_audit_log_list_v1")
		self.assertEqual(view["company"], "Korea Demo Co")
		self.assertEqual(view["workplaces"], ["Seoul HQ", "Busan Branch"])
		self.assertEqual(view["total_count"], 2)
		self.assertEqual([item["name"] for item in view["items"]], ["KPCRA-0002", "KPCRA-0001"])
		self.assertEqual(view["items"][0]["route"], "korea-payroll-review-audit-logs/KPCRA-0002")
		self.assertEqual(view["items"][0]["action"]["action"], "open_payroll_review_audit_log")
		self.assertFalse(view["items"][0]["action"]["requires_runtime_apply"])
		self.assertFalse(view["requires_runtime_apply"])
		self.assertTrue(view["requires_human_approval"])
		self.assertEqual(view["ai_role"], "assistant_only")

	def test_rejects_cross_scope_rows_in_strict_mode(self):
		with self.assertRaisesRegex(ValueError, "audit row company must match requested company"):
			self.mod.build_korea_payroll_review_audit_log_list(
				[audit_row(company="Other Co")],
				company="Korea Demo Co",
				workplaces=["Seoul HQ"],
				strict_scope=True,
			)

		with self.assertRaisesRegex(ValueError, "audit row workplace is outside requested workplaces"):
			self.mod.build_korea_payroll_review_audit_log_list(
				[audit_row(workplace="Incheon Branch")],
				company="Korea Demo Co",
				workplaces=["Seoul HQ"],
				strict_scope=True,
			)

	def test_accepts_runtime_api_wrapper_result_and_missing_created_at(self):
		api_row = audit_row(
			contract_type="korea_payroll_closing_review_audit_log_runtime_insert_api_v1",
			runtime_insert_contract_type="korea_payroll_closing_review_audit_log_runtime_insert_v1",
		)
		api_row.pop("created_at")

		view = self.mod.build_korea_payroll_review_audit_log_list([api_row], company="Korea Demo Co")

		self.assertEqual(view["total_count"], 1)
		self.assertEqual(view["items"][0]["source_contract_type"], "korea_payroll_closing_review_audit_log_runtime_insert_api_v1")
		self.assertIsNone(view["items"][0]["created_at"])

	def test_invalid_contract_flags_period_and_numeric_score_keys_fail_closed(self):
		bad_contract = audit_row(contract_type="korea_payroll_closing_review_audit_log_runtime_insert_api_v1")
		with self.assertRaisesRegex(ValueError, "runtime_insert_contract_type must be korea_payroll_closing_review_audit_log_runtime_insert_v1"):
			self.mod.build_korea_payroll_review_audit_log_list([bad_contract], company="Korea Demo Co")

		bad_previous = audit_row(previous_status="submitted")
		with self.assertRaisesRegex(ValueError, "previous_status must be draft_pending_human_approval"):
			self.mod.build_korea_payroll_review_audit_log_list([bad_previous], company="Korea Demo Co")

		bad_source = audit_row(source_audit_log_contract_type="evil_contract")
		with self.assertRaisesRegex(ValueError, "source_audit_log_contract_type must be korea_payroll_closing_draft_review_audit_log_v1"):
			self.mod.build_korea_payroll_review_audit_log_list([bad_source], company="Korea Demo Co")

		bad_period = audit_row(period_start="2026-06-30", period_end="2026-06-01")
		with self.assertRaisesRegex(ValueError, "period_start must be on or before period_end"):
			self.mod.build_korea_payroll_review_audit_log_list([bad_period], company="Korea Demo Co")

		bad_score = audit_row(audit_event={"legal": {"score": 0.91}})
		with self.assertRaisesRegex(ValueError, "score keys are not allowed"):
			self.mod.build_korea_payroll_review_audit_log_list([bad_score], company="Korea Demo Co")

		bad_numeric_risk = audit_row(audit_event={"legal_risk": 0.91})
		with self.assertRaisesRegex(ValueError, "numeric risk keys are not allowed"):
			self.mod.build_korea_payroll_review_audit_log_list([bad_numeric_risk], company="Korea Demo Co")

	def test_defensively_copies_inputs_and_outputs(self):
		row = audit_row()
		original = copy.deepcopy(row)

		view = self.mod.build_korea_payroll_review_audit_log_list([row], company="Korea Demo Co")
		view["items"][0]["source_audit_log"]["name"] = "MUTATED"

		self.assertEqual(row, original)

	def test_builds_route_only_audit_log_detail_for_selected_row(self):
		row = audit_row(name="AUDIT LOG/서울 1", created_at="2026-05-31T18:00:00+09:00")
		row["audit_event"] = {"action": "approve_draft", "status": "draft_human_approved"}
		row["source_runtime_apply"] = {"status": "draft_human_approved", "action": "approve_draft"}

		detail = self.mod.build_korea_payroll_review_audit_log_detail(
			row,
			company="Korea Demo Co",
			workplaces=["Seoul HQ"],
		)

		self.assertEqual(detail["contract_type"], "korea_payroll_review_audit_log_detail_v1")
		self.assertEqual(detail["source_contract_type"], "korea_payroll_closing_review_audit_log_runtime_insert_v1")
		self.assertEqual(detail["runtime_action"], "preview_only")
		self.assertFalse(detail["requires_runtime_apply"])
		self.assertEqual(detail["name"], "AUDIT LOG/서울 1")
		self.assertEqual(detail["route"], "korea-payroll-review-audit-logs/AUDIT%20LOG%2F%EC%84%9C%EC%9A%B8%201")
		self.assertEqual(detail["audit_event"]["action"], "approve_draft")
		self.assertEqual(detail["source_runtime_apply"]["status"], "draft_human_approved")
		self.assertEqual(
			detail["action"],
			{
				"action": "open_payroll_review_audit_log",
				"route": "korea-payroll-review-audit-logs/AUDIT%20LOG%2F%EC%84%9C%EC%9A%B8%201",
				"enabled": True,
				"requires_runtime_apply": False,
			},
		)
		self.assertTrue(detail["requires_human_approval"])
		self.assertEqual(detail["ai_role"], "assistant_only")

	def test_audit_log_detail_rejects_out_of_scope_workplace(self):
		row = audit_row(workplace="Busan Branch")

		with self.assertRaisesRegex(ValueError, "audit row workplace is outside requested workplaces"):
			self.mod.build_korea_payroll_review_audit_log_detail(
				row,
				company="Korea Demo Co",
				workplaces=["Seoul HQ"],
			)

	def test_audit_log_detail_rejects_forged_score_keys(self):
		row = audit_row(source_runtime_apply={"closing success rate": 0.9})

		with self.assertRaisesRegex(ValueError, "score keys are not allowed"):
			self.mod.build_korea_payroll_review_audit_log_detail(row, company="Korea Demo Co")


if __name__ == "__main__":
	unittest.main()
