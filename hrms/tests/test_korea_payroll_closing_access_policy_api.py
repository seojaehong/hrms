#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import types
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "payroll_closing_access_policy_api.py"


def load_module(with_fake_frappe: bool = False):
	old_frappe = sys.modules.get("frappe")
	if with_fake_frappe:
		fake = types.SimpleNamespace()
		fake.whitelist = lambda: (lambda fn: setattr(fn, "is_whitelisted_for_test", True) or fn)
		sys.modules["frappe"] = fake
	elif "frappe" in sys.modules:
		del sys.modules["frappe"]
	try:
		spec = importlib.util.spec_from_file_location("korea_payroll_closing_access_policy_api", MODULE_PATH)
		module = importlib.util.module_from_spec(spec)
		assert spec.loader is not None
		spec.loader.exec_module(module)
		return module
	finally:
		if old_frappe is not None:
			sys.modules["frappe"] = old_frappe
		elif "frappe" in sys.modules:
			del sys.modules["frappe"]


class TestKoreaPayrollClosingAccessPolicyApi(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()
		self.session = {
			"contract_type": "korea_payroll_closing_session_v1",
			"name": "KPC-2026-05-SEOUL",
			"company": "Korea Demo Co",
			"workplace": "Seoul HQ",
			"period_start": "2026-05-01",
			"period_end": "2026-05-31",
			"status": "blocked",
			"requires_human_approval": True,
			"ai_role": "assistant_only",
		}
		self.actor = {"user": "manager@example.com", "role": "branch_manager", "company": "Korea Demo Co", "workplaces": ["Seoul HQ"]}

	def test_previews_access_decision_from_dict_payloads_without_runtime_mutation(self):
		result = self.mod.preview_korea_payroll_closing_access_decision(
			session=self.session,
			actor=self.actor,
			action="record_human_review",
		)

		self.assertEqual(result["contract_type"], "korea_payroll_closing_access_decision_preview_v1")
		self.assertEqual(result["access_decision_contract_type"], "korea_payroll_closing_access_decision_v1")
		self.assertEqual(result["source_session_contract_type"], "korea_payroll_closing_session_v1")
		self.assertEqual(result["decision"], "allow")
		self.assertEqual(result["actor"], "manager@example.com")
		self.assertEqual(result["scope"]["workplace"], "Seoul HQ")
		self.assertEqual(result["runtime_action"], "preview_only")
		self.assertFalse(result["requires_runtime_apply"])
		self.assertTrue(result["requires_human_approval"])
		self.assertEqual(result["ai_role"], "assistant_only")
		self.assertFalse(self._contains_forbidden_numeric_score(result))

		self.actor["workplaces"].append("Busan Branch")
		self.assertEqual(result["scope"]["workplace"], "Seoul HQ")

	def test_previews_access_decision_from_json_payloads_and_preserves_denial(self):
		actor = {"user": "busan@example.com", "role": "branch_manager", "company": "Korea Demo Co", "workplaces": ["Busan Branch"]}

		result = self.mod.preview_korea_payroll_closing_access_decision(
			session=json.dumps(self.session),
			actor=json.dumps(actor),
			action="review_session",
		)

		self.assertEqual(result["contract_type"], "korea_payroll_closing_access_decision_preview_v1")
		self.assertEqual(result["decision"], "deny")
		self.assertEqual(result["reason"], "workplace_scope_mismatch")
		self.assertEqual(result["allowed_actions"], [])
		self.assertFalse(result["requires_runtime_apply"])

	def test_rejects_malformed_json_and_non_mapping_payloads_before_delegation(self):
		with self.assertRaisesRegex(ValueError, "session JSON payload is invalid"):
			self.mod.preview_korea_payroll_closing_access_decision(session='{"bad":', actor=self.actor, action="review_session")
		with self.assertRaisesRegex(ValueError, "session must be a dict or JSON object"):
			self.mod.preview_korea_payroll_closing_access_decision(session="[]", actor=self.actor, action="review_session")
		with self.assertRaisesRegex(ValueError, "actor must be a dict or JSON object"):
			self.mod.preview_korea_payroll_closing_access_decision(session=self.session, actor=[], action="review_session")

	def test_preserves_core_fail_closed_validation(self):
		with self.assertRaisesRegex(ValueError, "action must be one of"):
			self.mod.preview_korea_payroll_closing_access_decision(session=self.session, actor=self.actor, action="approve_payroll")
		with self.assertRaisesRegex(ValueError, "actor.workplaces must be a list"):
			self.mod.preview_korea_payroll_closing_access_decision(
				session=self.session,
				actor={"user": "manager@example.com", "role": "branch_manager", "company": "Korea Demo Co", "workplaces": "Seoul HQ"},
				action="review_session",
			)

	def test_preview_function_is_whitelisted_inside_frappe(self):
		module = load_module(with_fake_frappe=True)

		self.assertTrue(module.preview_korea_payroll_closing_access_decision.is_whitelisted_for_test)

	def _contains_forbidden_numeric_score(self, value):
		forbidden = {"risk_score", "score", "probability", "success_rate"}
		if isinstance(value, dict):
			return any(key in forbidden or self._contains_forbidden_numeric_score(child) for key, child in value.items())
		if isinstance(value, list):
			return any(self._contains_forbidden_numeric_score(child) for child in value)
		return False


if __name__ == "__main__":
	unittest.main()
