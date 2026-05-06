#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "payroll_closing_access_policy.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_payroll_closing_access_policy", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


class TestKoreaPayrollClosingAccessPolicy(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()
		self.session = {
			"contract_type": "korea_payroll_closing_session_v1",
			"company": "Korea Demo Co",
			"workplace": "Seoul HQ",
			"period_start": "2026-05-01",
			"period_end": "2026-05-31",
			"status": "blocked",
			"requires_human_approval": True,
			"ai_role": "assistant_only",
		}

	def test_hq_hr_admin_can_review_any_workplace_without_runtime_mutation(self):
		decision = self.mod.build_payroll_closing_access_decision(
			self.session,
			actor={"user": "hq@example.com", "role": "hq_hr_admin", "company": "Korea Demo Co"},
			action="review_session",
		)

		self.assertEqual(decision["contract_type"], "korea_payroll_closing_access_decision_v1")
		self.assertEqual(decision["actor"], "hq@example.com")
		self.assertEqual(decision["role"], "hq_hr_admin")
		self.assertEqual(decision["decision"], "allow")
		self.assertEqual(decision["allowed_actions"], ["review_session", "record_human_review", "request_approval"])
		self.assertEqual(decision["runtime_action"], "preview_only")
		self.assertFalse(decision["requires_runtime_apply"])
		self.assertTrue(decision["requires_human_approval"])
		self.assertEqual(decision["ai_role"], "assistant_only")
		self.assertFalse(self._contains_forbidden_numeric_score(decision))

	def test_branch_manager_is_limited_to_assigned_workplace(self):
		allowed = self.mod.build_payroll_closing_access_decision(
			self.session,
			actor={"user": "manager@example.com", "role": "branch_manager", "company": "Korea Demo Co", "workplaces": ["Seoul HQ"]},
			action="record_human_review",
		)
		self.assertEqual(allowed["decision"], "allow")
		self.assertEqual(allowed["scope"]["workplace"], "Seoul HQ")

		denied = self.mod.build_payroll_closing_access_decision(
			self.session,
			actor={"user": "busan@example.com", "role": "branch_manager", "company": "Korea Demo Co", "workplaces": ["Busan Branch"]},
			action="review_session",
		)
		self.assertEqual(denied["decision"], "deny")
		self.assertEqual(denied["reason"], "workplace_scope_mismatch")
		self.assertEqual(denied["allowed_actions"], [])

	def test_employee_is_denied_and_external_advisor_is_read_only_when_assigned(self):
		employee = self.mod.build_payroll_closing_access_decision(
			self.session,
			actor={"user": "emp@example.com", "role": "employee", "company": "Korea Demo Co", "workplaces": ["Seoul HQ"]},
			action="review_session",
		)
		self.assertEqual(employee["decision"], "deny")
		self.assertEqual(employee["reason"], "role_not_allowed")

		advisor = self.mod.build_payroll_closing_access_decision(
			self.session,
			actor={"user": "advisor@example.com", "role": "external_labor_advisor", "company": "Korea Demo Co", "workplaces": ["Seoul HQ"]},
			action="record_human_review",
		)
		self.assertEqual(advisor["decision"], "deny")
		self.assertEqual(advisor["reason"], "action_not_allowed")
		self.assertEqual(advisor["allowed_actions"], ["review_session"])

		advisor_read = self.mod.build_payroll_closing_access_decision(
			self.session,
			actor={"user": "advisor@example.com", "role": "external_labor_advisor", "company": "Korea Demo Co", "workplaces": ["Seoul HQ"]},
			action="review_session",
		)
		self.assertEqual(advisor_read["decision"], "allow")
		self.assertEqual(advisor_read["allowed_actions"], ["review_session"])

	def test_invalid_session_actor_and_action_fail_closed(self):
		with self.assertRaisesRegex(ValueError, "session.contract_type must be korea_payroll_closing_session_v1"):
			self.mod.build_payroll_closing_access_decision({}, actor={"user": "hq@example.com", "role": "hq_hr_admin", "company": "Korea Demo Co"}, action="review_session")
		with self.assertRaisesRegex(ValueError, "session.company is required"):
			self.mod.build_payroll_closing_access_decision({**self.session, "company": " "}, actor={"user": "hq@example.com", "role": "hq_hr_admin", "company": "Korea Demo Co"}, action="review_session")
		with self.assertRaisesRegex(ValueError, "actor must be a dict"):
			self.mod.build_payroll_closing_access_decision(self.session, actor=[], action="review_session")
		with self.assertRaisesRegex(ValueError, "actor.role must be one of"):
			self.mod.build_payroll_closing_access_decision(self.session, actor={"user": "ops@example.com", "role": "owner", "company": "Korea Demo Co"}, action="review_session")
		with self.assertRaisesRegex(ValueError, "action must be one of"):
			self.mod.build_payroll_closing_access_decision(self.session, actor={"user": "hq@example.com", "role": "hq_hr_admin", "company": "Korea Demo Co"}, action="approve_payroll")
		with self.assertRaisesRegex(ValueError, "actor.company must match session company"):
			self.mod.build_payroll_closing_access_decision(self.session, actor={"user": "hq@example.com", "role": "hq_hr_admin", "company": "Other Co"}, action="review_session")
		with self.assertRaisesRegex(ValueError, "actor.workplaces must be a list"):
			self.mod.build_payroll_closing_access_decision(self.session, actor={"user": "manager@example.com", "role": "branch_manager", "company": "Korea Demo Co", "workplaces": "Seoul HQ"}, action="review_session")
		with self.assertRaisesRegex(ValueError, "session.name must be a string"):
			self.mod.build_payroll_closing_access_decision({**self.session, "name": {"bad": "ref"}}, actor={"user": "hq@example.com", "role": "hq_hr_admin", "company": "Korea Demo Co"}, action="review_session")

	def _contains_forbidden_numeric_score(self, value):
		forbidden = {"risk_score", "score", "probability", "success_rate"}
		if isinstance(value, dict):
			return any(key in forbidden or self._contains_forbidden_numeric_score(child) for key, child in value.items())
		if isinstance(value, list):
			return any(self._contains_forbidden_numeric_score(child) for child in value)
		return False


if __name__ == "__main__":
	unittest.main()
