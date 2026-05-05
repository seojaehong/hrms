#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import types
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "closing_center_api.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_closing_center_api", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


class TestKoreaClosingCenterApi(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()
		self.period = {"start_date": "2026-05-01", "end_date": "2026-05-31"}

	def test_previews_closing_center_from_json_items_without_runtime_mutation(self):
		items = [
			{
				"doctype": "Korea Attendance Closing",
				"name": "ATT-SEOUL-MAY",
				"workplace": "SEOUL-01",
				"status": "Blocked",
				"blockers": ["E-001: unmarked attendance remains before closing"],
				"metrics": {"employees": 12, "unmarked_days": 3},
			},
			{
				"doctype": "Korea Payroll Verification",
				"name": "PAY-SEOUL-MAY",
				"workplace": "SEOUL-01",
				"status": "Ready",
			},
		]

		result = self.mod.preview_korea_closing_center(
			workplace="SEOUL-01",
			period=json.dumps(self.period),
			items=json.dumps(items),
		)

		self.assertEqual(result["contract_type"], "korea_closing_center_preview_v1")
		self.assertEqual(result["runtime_action"], "preview_only")
		self.assertFalse(result["requires_runtime_apply"])
		self.assertEqual(result["center"]["workplace"], "SEOUL-01")
		self.assertEqual(result["center"]["summary"], {"total_items": 2, "blocked_items": 1, "ready_items": 1, "closed_items": 0})
		self.assertEqual(result["center"]["cards"][0]["name"], "ATT-SEOUL-MAY")

	def test_preview_wrapper_does_not_let_downstream_helper_mutate_caller_inputs(self):
		period = {"start_date": "2026-05-01", "end_date": "2026-05-31"}
		items = [{"doctype": "Korea Attendance Closing", "name": "ATT-1", "workplace": "SEOUL-01", "status": "Ready"}]

		class MutatingClosingHelper:
			@staticmethod
			def build_closing_center(*, workplace, period, items):
				period["start_date"] = "2099-01-01"
				items[0]["status"] = "MUTATED"
				return {"contract_type": "mutating_helper", "workplace": workplace, "period": period, "items": items}

		self.mod._load_sibling_module = lambda *_args: MutatingClosingHelper

		result = self.mod.preview_korea_closing_center(workplace="SEOUL-01", period=period, items=items)
		result["center"]["items"][0]["status"] = "RETURN_MUTATED"

		self.assertEqual(period, {"start_date": "2026-05-01", "end_date": "2026-05-31"})
		self.assertEqual(items, [{"doctype": "Korea Attendance Closing", "name": "ATT-1", "workplace": "SEOUL-01", "status": "Ready"}])

	def test_frappe_present_import_applies_whitelist_decorator(self):
		calls = []

		def whitelist():
			def decorator(fn):
				calls.append(fn.__name__)
				fn.is_whitelisted_for_test = True
				return fn

			return decorator

		fake_frappe = types.SimpleNamespace(whitelist=whitelist)
		old_frappe = sys.modules.get("frappe")
		sys.modules["frappe"] = fake_frappe
		try:
			module = load_module()
		finally:
			if old_frappe is None:
				sys.modules.pop("frappe", None)
			else:
				sys.modules["frappe"] = old_frappe

		self.assertEqual(calls, ["preview_korea_closing_center"])
		self.assertTrue(module.preview_korea_closing_center.is_whitelisted_for_test)

	def test_rejects_malformed_json_non_object_period_and_non_list_items(self):
		with self.assertRaisesRegex(ValueError, "JSON payload is invalid"):
			self.mod.preview_korea_closing_center(workplace="SEOUL-01", period="{", items=[])

		with self.assertRaisesRegex(ValueError, "period must be a dict or JSON object"):
			self.mod.preview_korea_closing_center(workplace="SEOUL-01", period=[], items=[])

		with self.assertRaisesRegex(ValueError, "items must be a list or JSON array"):
			self.mod.preview_korea_closing_center(workplace="SEOUL-01", period=self.period, items={"not": "a list"})


if __name__ == "__main__":
	unittest.main()
