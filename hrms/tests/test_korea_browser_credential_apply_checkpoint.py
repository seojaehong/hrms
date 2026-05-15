#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import sys
import unittest

SCRIPT_PATH = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "verify_korea_demo_browser_credential_apply.py"


def load_module():
	spec = importlib.util.spec_from_file_location("verify_korea_demo_browser_credential_apply", SCRIPT_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


class TestKoreaBrowserCredentialApplyCheckpoint(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()
		self.repo_root = pathlib.Path(__file__).resolve().parents[2]

	def test_checkpoint_fails_closed_when_password_env_missing(self):
		report = self.mod.verify_demo_browser_credential_apply(
			repo_root=self.repo_root,
			environ={},
			human_approved=True,
			dry_run=True,
		)

		self.assertEqual(report["contract_type"], "korea_demo_browser_credential_apply_checkpoint_v1")
		self.assertEqual(report["runtime_action"], "credential_apply_and_browser_verification_checkpoint")
		self.assertTrue(report["requires_human_approval"])
		self.assertEqual(report["ai_role"], "assistant_only")
		self.assertEqual(report["mutation_boundary"], "credential_only_then_browser_read_only_no_payroll_submit_approve_send_provider_call")
		self.assertFalse(report["credential_apply"]["attempted"])
		self.assertEqual(report["credential_apply"]["reason"], "FRAPPE_BROWSER_PASSWORD missing")
		self.assertFalse(report["runtime_verified"])
		self.assertTrue(report["fixture_fallback_required"])
		self.assertNotIn("runtime-secret", json.dumps(report))

	def test_checkpoint_requires_explicit_human_approval_before_apply(self):
		report = self.mod.verify_demo_browser_credential_apply(
			repo_root=self.repo_root,
			environ={"FRAPPE_BROWSER_PASSWORD": "runtime-secret"},
			human_approved=False,
			dry_run=True,
		)

		self.assertFalse(report["credential_apply"]["attempted"])
		self.assertEqual(report["credential_apply"]["reason"], "human approval flag missing")
		self.assertFalse(report["runtime_verified"])
		self.assertNotIn("runtime-secret", json.dumps(report))

	def test_checkpoint_builds_redacted_apply_and_browser_commands(self):
		commands = []

		def fake_run(command, **kwargs):
			commands.append({"command": command, "kwargs": kwargs})
			if command[0:2] == ["docker", "compose"]:
				return self.mod.CommandResult(
					returncode=0,
					stdout=json.dumps({
						"contract_type": "korea_demo_browser_credential_runtime_apply_v1",
						"runtime_action": "demo_credential_runtime_apply",
						"credential_ready_for_browser_verifier": True,
						"human_approval_verified": True,
						"requires_human_approval": True,
						"ai_role": "assistant_only",
					}),
					stderr="",
				)
			return self.mod.CommandResult(
				returncode=0,
				stdout=json.dumps({
					"contract_type": "korea_payroll_closing_browser_runtime_walkthrough_v1",
					"runtime_action": "browser_runtime_read_only",
					"requires_runtime_apply": False,
					"requires_human_approval": True,
					"ai_role": "assistant_only",
					"mutation_boundary": "read_only_no_save_submit_approve_send_provider",
					"runtime_verified": True,
					"fixture_fallback_required": False,
				}),
				stderr="",
			)

		report = self.mod.verify_demo_browser_credential_apply(
			repo_root=self.repo_root,
			environ={"FRAPPE_BROWSER_PASSWORD": "runtime-secret"},
			human_approved=True,
			run_command=fake_run,
		)

		self.assertTrue(report["credential_apply"]["attempted"])
		self.assertTrue(report["credential_apply"]["passed"])
		self.assertTrue(report["browser_verification"]["attempted"])
		self.assertTrue(report["runtime_verified"])
		self.assertFalse(report["fixture_fallback_required"])
		serialized = json.dumps(report, ensure_ascii=False)
		self.assertIn("[redacted]", serialized)
		self.assertNotIn("runtime-secret", serialized)
		self.assertEqual(commands[0]["kwargs"]["env"]["FRAPPE_BROWSER_PASSWORD"], "runtime-secret")
		self.assertEqual(commands[1]["kwargs"]["env"]["FRAPPE_BROWSER_PASSWORD"], "runtime-secret")

	def test_checkpoint_rejects_browser_positive_without_safety_metadata(self):
		def fake_run(command, **kwargs):
			if command[0:2] == ["docker", "compose"]:
				return self.mod.CommandResult(
					returncode=0,
					stdout=json.dumps({
						"contract_type": "korea_demo_browser_credential_runtime_apply_v1",
						"runtime_action": "demo_credential_runtime_apply",
						"credential_ready_for_browser_verifier": True,
						"human_approval_verified": True,
					}),
					stderr="",
				)
			return self.mod.CommandResult(
				returncode=0,
				stdout=json.dumps({
					"contract_type": "korea_payroll_closing_browser_runtime_walkthrough_v1",
					"runtime_action": "browser_runtime_read_only",
					"runtime_verified": True,
					"fixture_fallback_required": False,
					"requires_human_approval": False,
					"ai_role": "automation",
				}),
				stderr="",
			)

		report = self.mod.verify_demo_browser_credential_apply(
			repo_root=self.repo_root,
			environ={"FRAPPE_BROWSER_PASSWORD": "runtime-secret"},
			human_approved=True,
			run_command=fake_run,
		)

		self.assertTrue(report["browser_verification"]["attempted"])
		self.assertFalse(report["browser_verification"]["passed"])
		self.assertFalse(report["browser_verification"]["runtime_verified"])
		self.assertFalse(report["runtime_verified"])
		self.assertTrue(report["fixture_fallback_required"])
		self.assertIn("browser verifier safety metadata invalid", report["browser_verification"]["reason"])

	def test_checkpoint_does_not_run_browser_when_credential_apply_fails(self):
		commands = []

		def fake_run(command, **kwargs):
			commands.append(command)
			return self.mod.CommandResult(returncode=1, stdout="", stderr="apply failed")

		report = self.mod.verify_demo_browser_credential_apply(
			repo_root=self.repo_root,
			environ={"FRAPPE_BROWSER_PASSWORD": "runtime-secret"},
			human_approved=True,
			run_command=fake_run,
		)

		self.assertEqual(len(commands), 1)
		self.assertTrue(report["credential_apply"]["attempted"])
		self.assertFalse(report["credential_apply"]["passed"])
		self.assertFalse(report["browser_verification"]["attempted"])
		self.assertFalse(report["runtime_verified"])
		self.assertNotIn("runtime-secret", json.dumps(report))


if __name__ == "__main__":
	unittest.main()
