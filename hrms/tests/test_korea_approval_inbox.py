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


if __name__ == "__main__":
	unittest.main()
