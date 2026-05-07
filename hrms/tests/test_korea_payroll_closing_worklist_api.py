#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import types
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "payroll_closing_worklist_api.py"


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
		spec = importlib.util.spec_from_file_location("korea_payroll_closing_worklist_api", MODULE_PATH)
		module = importlib.util.module_from_spec(spec)
		assert spec.loader is not None
		spec.loader.exec_module(module)
		return module
	finally:
		if old_frappe is not None:
			sys.modules["frappe"] = old_frappe
		else:
			sys.modules.pop("frappe", None)


class TestKoreaPayrollClosingWorklistApi(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()
		self.blocked_session = self._session(
			name="KPCS-2026-05-SEOUL",
			workplace="Seoul HQ",
			status="blocked",
			blockers=[{"code": "attendance_not_ready"}],
			next_actions=[{"action": "resolve_attendance_blockers", "label": "Resolve attendance blockers"}],
		)
		self.ready_session = self._session(
			name="KPCS-2026-05-BUSAN",
			workplace="Busan Branch",
			status="review_ready",
			blockers=[],
			next_actions=[{"action": "request_human_approval", "label": "Request final human approval"}],
		)

	def test_preview_api_builds_route_only_worklist_from_json_payloads(self):
		result = self.mod.preview_korea_payroll_closing_worklist(
			company="Korea Demo Co",
			sessions=json.dumps([self.ready_session, self.blocked_session]),
			workplaces=json.dumps(["Seoul HQ", "Busan Branch"]),
		)

		self.assertEqual(result["contract_type"], "korea_payroll_closing_worklist_preview_v1")
		self.assertEqual(result["worklist_contract_type"], "korea_payroll_closing_worklist_v1")
		self.assertEqual(result["runtime_action"], "preview_only")
		self.assertFalse(result["requires_runtime_apply"])
		self.assertTrue(result["requires_human_approval"])
		self.assertEqual(result["ai_role"], "assistant_only")
		self.assertEqual(result["summary"], {"total_count": 2, "blocked_count": 1, "review_ready_count": 1})
		self.assertEqual([item["name"] for item in result["items"]], ["KPCS-2026-05-SEOUL", "KPCS-2026-05-BUSAN"])
		self.assertEqual(result["items"][0]["route"], "korea-payroll-closing-session/KPCS-2026-05-SEOUL")
		self.assertFalse(result["items"][0]["primary_action"]["requires_runtime_apply"])
		self.assertFalse(self._contains_forbidden_numeric_score(result))

	def test_preview_api_filters_workplaces_and_defensive_copies_inputs_and_outputs(self):
		sessions = [json.loads(json.dumps(self.blocked_session)), json.loads(json.dumps(self.ready_session))]
		workplaces = ["Busan Branch"]
		original = json.loads(json.dumps({"sessions": sessions, "workplaces": workplaces}))

		result = self.mod.preview_korea_payroll_closing_worklist(
			company="Korea Demo Co",
			sessions=sessions,
			workplaces=workplaces,
		)

		self.assertEqual(result["summary"], {"total_count": 1, "blocked_count": 0, "review_ready_count": 1})
		self.assertEqual(result["items"][0]["workplace"], "Busan Branch")
		self.assertEqual({"sessions": sessions, "workplaces": workplaces}, original)
		result["items"][0]["name"] = "MUTATED"
		self.assertEqual(sessions[1]["name"], "KPCS-2026-05-BUSAN")

	def test_preview_api_rejects_invalid_payloads_before_delegation(self):
		with self.assertRaisesRegex(ValueError, "JSON payload is invalid"):
			self.mod.preview_korea_payroll_closing_worklist(company="Korea Demo Co", sessions='[{"bad":', workplaces=None)

		with self.assertRaisesRegex(ValueError, "sessions must be a list or JSON array"):
			self.mod.preview_korea_payroll_closing_worklist(company="Korea Demo Co", sessions='{"not":"a-list"}', workplaces=None)

		with self.assertRaisesRegex(ValueError, "workplaces must be a list or JSON array"):
			self.mod.preview_korea_payroll_closing_worklist(company="Korea Demo Co", sessions=[], workplaces='{"not":"a-list"}')

	def test_preview_api_is_whitelisted_when_frappe_is_available(self):
		module = load_module(with_frappe=True)
		self.assertTrue(module.preview_korea_payroll_closing_worklist.is_whitelisted_for_test)

	def _session(self, *, name: str, workplace: str, status: str, blockers: list[dict], next_actions: list[dict]) -> dict:
		return {
			"contract_type": "korea_payroll_closing_session_v1",
			"name": name,
			"company": "Korea Demo Co",
			"workplace": workplace,
			"period_start": "2026-05-01",
			"period_end": "2026-05-31",
			"status": status,
			"blockers": blockers,
			"next_actions": next_actions,
			"payroll_artifacts": {"payroll_entry": f"PAY-{name}"},
			"requires_human_approval": True,
			"ai_role": "assistant_only",
		}

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
