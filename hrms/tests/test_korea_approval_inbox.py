#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import importlib.util
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "approval_inbox.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_approval_inbox", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


class TestUnifiedApprovalInbox(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()

	def test_normalizes_mixed_approval_sources_by_actor(self):
		items = self.mod.build_approval_inbox(
			[
				{"doctype": "Leave Application", "name": "LA-1", "employee": "EMP-1", "approver": "manager@example.com", "posting_date": dt.date(2026, 5, 2), "status": "Open"},
				{"doctype": "Expense Claim", "name": "EC-1", "employee": "EMP-2", "approver": "finance@example.com", "posting_date": "2026-05-01", "status": "Pending"},
				{"doctype": "Shift Request", "name": "SR-1", "employee": "EMP-3", "approver": "manager@example.com", "posting_date": dt.date(2026, 5, 3), "status": "Approved"},
			],
			actor="manager@example.com",
			today=dt.date(2026, 5, 3),
		)

		self.assertEqual([item["name"] for item in items], ["LA-1"])
		self.assertEqual(items[0]["source_doctype"], "Leave Application")
		self.assertEqual(items[0]["priority"], "Normal")

	def test_overdue_open_items_are_high_priority_and_sorted_oldest_first(self):
		items = self.mod.build_approval_inbox(
			[
				{"doctype": "Expense Claim", "name": "EC-2", "employee": "EMP-2", "approver": "manager@example.com", "posting_date": "2026-04-20", "status": "Open"},
				{"doctype": "Leave Application", "name": "LA-2", "employee": "EMP-1", "approver": "manager@example.com", "posting_date": "2026-05-01", "status": "Open"},
			],
			actor="manager@example.com",
			today=dt.date(2026, 5, 3),
			overdue_after_days=5,
		)

		self.assertEqual([item["name"] for item in items], ["EC-2", "LA-2"])
		self.assertEqual(items[0]["priority"], "High")
		self.assertTrue(items[0]["overdue"])

	def test_inbox_summary_counts_items_by_source(self):
		self.assertEqual(self.mod.summarize_inbox([{"source_doctype": "Leave Application"}, {"source_doctype": "Leave Application"}, {"source_doctype": "Expense Claim"}]), {"Leave Application": 2, "Expense Claim": 1})

	def test_builds_single_approval_action_contract_for_open_assigned_item(self):
		item = {
			"source_doctype": "Leave Application",
			"name": "LA-1",
			"approver": "manager@example.com",
			"status": "Open",
		}

		action = self.mod.build_approval_action(
			item,
			action="approve",
			actor="manager@example.com",
			note="Looks good",
		)

		self.assertEqual(action["action_type"], "korea_approval_action_v1")
		self.assertEqual(action["action"], "approve")
		self.assertEqual(action["target"], {"doctype": "Leave Application", "name": "LA-1"})
		self.assertEqual(action["actor"], "manager@example.com")
		self.assertEqual(action["note"], "Looks good")
		self.assertEqual(action["result_status"], "Approved")
		self.assertTrue(action["requires_runtime_apply"])

	def test_builds_batch_action_contract_preserving_order_and_summary(self):
		items = [
			{"source_doctype": "Leave Application", "name": "LA-1", "approver": "manager@example.com", "status": "Open"},
			{"source_doctype": "Expense Claim", "name": "EC-1", "approver": "manager@example.com", "status": "Pending"},
		]

		batch = self.mod.build_approval_batch_action(
			items,
			action="reject",
			actor="manager@example.com",
			note="Missing evidence",
		)

		self.assertEqual(batch["batch_type"], "korea_approval_batch_action_v1")
		self.assertEqual(batch["actor"], "manager@example.com")
		self.assertEqual(batch["action"], "reject")
		self.assertEqual([entry["target"]["name"] for entry in batch["actions"]], ["LA-1", "EC-1"])
		self.assertEqual(batch["summary"], {"total": 2, "by_doctype": {"Leave Application": 1, "Expense Claim": 1}})

	def test_approval_action_rejects_wrong_actor_closed_item_and_invalid_action(self):
		open_item = {"source_doctype": "Leave Application", "name": "LA-1", "approver": "manager@example.com", "status": "Open"}
		closed_item = {"source_doctype": "Leave Application", "name": "LA-2", "approver": "manager@example.com", "status": "Approved"}

		with self.assertRaises(ValueError):
			self.mod.build_approval_action(open_item, action="approve", actor="other@example.com")
		with self.assertRaises(ValueError):
			self.mod.build_approval_action(closed_item, action="reject", actor="manager@example.com")
		with self.assertRaises(ValueError):
			self.mod.build_approval_action(open_item, action="delegate", actor="manager@example.com")

	def test_batch_action_rejects_empty_selection(self):
		with self.assertRaises(ValueError):
			self.mod.build_approval_batch_action([], action="approve", actor="manager@example.com")


if __name__ == "__main__":
	unittest.main()
