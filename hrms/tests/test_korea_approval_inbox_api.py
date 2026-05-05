#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "approval_inbox_api.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_approval_inbox_api", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


class TestKoreaApprovalInboxApi(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()
		self.records = [
			{
				"doctype": "Leave Application",
				"name": "LA-API-1",
				"employee": "EMP-0001",
				"approver": "manager@example.com",
				"posting_date": "2026-05-01",
				"status": "Open",
			},
			{
				"doctype": "Expense Claim",
				"name": "EC-API-1",
				"employee": "EMP-0002",
				"approver": "finance@example.com",
				"posting_date": "2026-05-02",
				"status": "Pending",
			},
		]

	def test_preview_inbox_accepts_json_records_without_frappe_mutation(self):
		payload = self.mod.preview_korea_approval_inbox(
			records=json.dumps(self.records),
			actor="manager@example.com",
			today="2026-05-05",
			overdue_after_days=3,
		)

		self.assertEqual(payload["contract_type"], "korea_approval_inbox_preview_v1")
		self.assertEqual([item["name"] for item in payload["items"]], ["LA-API-1"])
		self.assertEqual(payload["summary"], {"Leave Application": 1})
		self.assertEqual(payload["runtime_action"], "preview_only")
		self.assertFalse(payload["requires_runtime_apply"])

	def test_preview_action_builds_side_effect_free_runtime_contract(self):
		payload = self.mod.preview_korea_approval_action(
			item=json.dumps(
				{
					"source_doctype": "Leave Application",
					"name": "LA-API-1",
					"approver": "manager@example.com",
					"status": "Open",
				}
			),
			action="approve",
			actor="manager@example.com",
			note="Approved from mobile preview",
		)

		self.assertEqual(payload["contract_type"], "korea_approval_action_preview_v1")
		self.assertEqual(payload["target"], {"doctype": "Leave Application", "name": "LA-API-1"})
		self.assertEqual(payload["result_status"], "Approved")
		self.assertEqual(payload["runtime_action"], "preview_only")
		self.assertTrue(payload["requires_runtime_apply"])

	def test_preview_batch_action_rejects_empty_selection_and_preserves_order(self):
		with self.assertRaisesRegex(ValueError, "at least one approval item is required"):
			self.mod.preview_korea_approval_batch_action(items="[]", action="approve", actor="manager@example.com")

		payload = self.mod.preview_korea_approval_batch_action(
			items=json.dumps(
				[
					{"source_doctype": "Leave Application", "name": "LA-API-1", "approver": "manager@example.com", "status": "Open"},
					{"source_doctype": "Expense Claim", "name": "EC-API-1", "approver": "manager@example.com", "status": "Pending"},
				]
			),
			action="reject",
			actor="manager@example.com",
			note="Missing attachment",
		)

		self.assertEqual(payload["contract_type"], "korea_approval_batch_action_preview_v1")
		self.assertEqual([entry["target"]["name"] for entry in payload["actions"]], ["LA-API-1", "EC-API-1"])
		self.assertEqual(payload["summary"], {"total": 2, "by_doctype": {"Leave Application": 1, "Expense Claim": 1}})
		self.assertTrue(payload["requires_runtime_apply"])

	def test_invalid_json_and_payload_shapes_are_rejected_before_runtime_lookup(self):
		with self.assertRaisesRegex(ValueError, "JSON payload is invalid"):
			self.mod.preview_korea_approval_inbox(records='[{"name":', actor="manager@example.com")

		with self.assertRaisesRegex(ValueError, "records must be a list or JSON array"):
			self.mod.preview_korea_approval_inbox(records='{}', actor="manager@example.com")

		with self.assertRaisesRegex(ValueError, "item must be a dict or JSON object"):
			self.mod.preview_korea_approval_action(item="[]", action="approve", actor="manager@example.com")

	def test_wrong_actor_and_closed_items_stay_blocked_in_api_wrapper(self):
		with self.assertRaisesRegex(ValueError, "actor is not the assigned approver"):
			self.mod.preview_korea_approval_action(
				item={"source_doctype": "Leave Application", "name": "LA-API-1", "approver": "manager@example.com", "status": "Open"},
				action="approve",
				actor="other@example.com",
			)

		with self.assertRaisesRegex(ValueError, "only open approval items can be actioned"):
			self.mod.preview_korea_approval_action(
				item={"source_doctype": "Leave Application", "name": "LA-API-1", "approver": "manager@example.com", "status": "Approved"},
				action="reject",
				actor="manager@example.com",
			)


if __name__ == "__main__":
	unittest.main()
