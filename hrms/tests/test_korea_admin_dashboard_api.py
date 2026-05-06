#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import types
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "admin_dashboard_api.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_admin_dashboard_api", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


class TestKoreaAdminDashboardPreviewApi(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()

	def test_previews_admin_dashboard_from_json_metrics_without_runtime_mutation(self):
		preview = self.mod.preview_korea_admin_dashboard(
			metrics=json.dumps(
				{
					"open_approvals": "2",
					"overdue_compliance": 0,
					"pending_payslips": 4,
					"unclosed_attendance": 1,
				}
			)
		)

		self.assertEqual(preview["contract_type"], "korea_admin_dashboard_preview_v1")
		self.assertEqual(preview["runtime_action"], "preview_only")
		self.assertFalse(preview["requires_runtime_apply"])
		self.assertEqual(preview["dashboard"]["status"], "Needs Attention")
		self.assertEqual(
			[card["key"] for card in preview["dashboard"]["cards"]],
			[
				"open_approvals",
				"overdue_compliance",
				"pending_payslips",
				"unclosed_attendance",
				"blocked_payroll_closings",
			],
		)
		approvals = next(card for card in preview["dashboard"]["cards"] if card["key"] == "open_approvals")
		self.assertEqual(approvals["value"], 2)
		self.assertEqual(approvals["action"], {"action": "review_approval_inbox", "route": "korea-approval-inbox", "enabled": True, "requires_runtime_apply": False})

	def test_preview_does_not_let_downstream_builder_mutate_caller_input_or_return_reference(self):
		metrics = {"open_approvals": 1, "nested": {"value": "original"}}

		class MutatingDashboard:
			@staticmethod
			def build_admin_dashboard(*, metrics):
				metrics["open_approvals"] = 999
				metrics["nested"]["value"] = "mutated"
				return {"status": "Ready", "cards": [{"key": "open_approvals", "value": metrics["open_approvals"], "nested": metrics["nested"]}]}

		self.mod._load_sibling_module = lambda *_args: MutatingDashboard
		preview = self.mod.preview_korea_admin_dashboard(metrics=metrics)
		preview["dashboard"]["cards"][0]["nested"]["value"] = "return-mutated"

		self.assertEqual(metrics, {"open_approvals": 1, "nested": {"value": "original"}})

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

		self.assertEqual(calls, ["preview_korea_admin_dashboard"])
		self.assertTrue(module.preview_korea_admin_dashboard.is_whitelisted_for_test)

	def test_invalid_json_and_non_mapping_metrics_are_rejected_before_runtime_lookup(self):
		def fail_if_loaded(*_args):
			raise AssertionError("runtime module lookup should not happen for invalid metrics")

		self.mod._load_sibling_module = fail_if_loaded

		with self.assertRaisesRegex(ValueError, "JSON payload is invalid"):
			self.mod.preview_korea_admin_dashboard(metrics='{"open_approvals":')

		with self.assertRaisesRegex(ValueError, "metrics must be a dict or JSON object"):
			self.mod.preview_korea_admin_dashboard(metrics="[]")

	def test_bool_and_fractional_metric_counts_keep_field_specific_errors(self):
		with self.assertRaisesRegex(ValueError, "open_approvals must be a non-negative integer"):
			self.mod.preview_korea_admin_dashboard(metrics={"open_approvals": True})

		with self.assertRaisesRegex(ValueError, "pending_payslips must be a non-negative integer"):
			self.mod.preview_korea_admin_dashboard(metrics={"pending_payslips": "1.5"})


if __name__ == "__main__":
	unittest.main()
