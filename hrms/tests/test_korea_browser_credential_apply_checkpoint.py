#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile
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

	def test_checkpoint_rejects_blank_password_env_before_apply(self):
		report = self.mod.verify_demo_browser_credential_apply(
			repo_root=self.repo_root,
			environ={"FRAPPE_BROWSER_PASSWORD": "   \t\n"},
			human_approved=True,
			dry_run=True,
		)

		self.assertFalse(report["credential_apply"]["attempted"])
		self.assertEqual(report["credential_apply"]["reason"], "FRAPPE_BROWSER_PASSWORD blank")
		self.assertFalse(report["browser_verification"]["attempted"])
		self.assertFalse(report["runtime_verified"])
		self.assertTrue(report["fixture_fallback_required"])

	def test_checkpoint_fails_closed_when_required_scope_input_blank(self):
		valid_scope = {
			"site": "hrms.localhost",
			"company": "노란봉투법 데모",
			"base_url": "http://hrms.localhost:8000",
			"username": "demo.hr.manager@node.pe.kr",
			"chromium": "chromium-browser",
		}
		provided_flag_by_field = {
			"site": "site_provided",
			"company": "company_provided",
			"base_url": "base_url_provided",
			"username": "username_provided",
			"chromium": "chromium_provided",
		}
		for field in valid_scope:
			with self.subTest(field=field):
				commands = []

				def fake_run(command, **kwargs):
					commands.append(command)
					return self.mod.CommandResult(returncode=0, stdout="{}", stderr="")

				scope = {**valid_scope, field: "  \t\n"}
				report = self.mod.verify_demo_browser_credential_apply(
					repo_root=self.repo_root,
					environ={"FRAPPE_BROWSER_PASSWORD": "runtime-secret"},
					human_approved=True,
					run_command=fake_run,
					**scope,
				)

				self.assertEqual(commands, [])
				self.assertFalse(report["scope"][provided_flag_by_field[field]])
				self.assertFalse(report["credential_apply"]["attempted"])
				self.assertFalse(report["credential_apply"]["passed"])
				self.assertEqual(report["credential_apply"]["reason"], f"{field} must be a non-empty string")
				self.assertFalse(report["browser_verification"]["attempted"])
				self.assertEqual(report["browser_verification"]["reason"], "credential apply not ready")
				self.assertFalse(report["runtime_verified"])
				self.assertTrue(report["fixture_fallback_required"])
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
						"requires_runtime_apply": False,
						"credential_ready_for_browser_verifier": True,
						"human_approval_verified": True,
						"mutation_boundary": "credential_only_no_payroll_submit_approve_send_provider_call",
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
		# bench `execute --kwargs` parses the value as a Python literal, NOT JSON.
		# JSON `{"human_approved": true}` raises `NameError: true` on the bench side.
		# Verify the credential apply command passes a Python dict literal (`True`, capital T),
		# not a JSON `true`, inside the bash -lc payload. shlex/bash escaping may inject quote
		# sequences (`'"'"'`) between characters, so check for the unescaped tokens after a
		# best-effort normalization.
		bench_payload = commands[0]["command"][-1]
		normalized = bench_payload.replace("'\"'\"'", "'").replace("\\'", "'")
		self.assertIn("'human_approved': True", normalized)
		self.assertNotIn('"human_approved": true', bench_payload)

	def test_checkpoint_rejects_blank_browser_report_file_before_credential_apply(self):
		commands = []

		def fake_run(command, **kwargs):
			commands.append(command)
			return self.mod.CommandResult(returncode=0, stdout="{}", stderr="")

		report = self.mod.verify_demo_browser_credential_apply(
			repo_root=self.repo_root,
			environ={"FRAPPE_BROWSER_PASSWORD": "runtime-secret"},
			human_approved=True,
			browser_report_file="  \t\n",
			run_command=fake_run,
		)

		self.assertEqual(commands, [])
		self.assertFalse(report["credential_apply"]["attempted"])
		self.assertEqual(report["credential_apply"]["reason"], "browser_report_file must be a non-empty string")
		self.assertFalse(report["browser_verification"]["attempted"])
		self.assertEqual(report["browser_verification"]["reason"], "credential apply not ready")
		self.assertFalse(report["runtime_verified"])
		self.assertTrue(report["fixture_fallback_required"])
		self.assertNotIn("runtime-secret", json.dumps(report))

	def test_checkpoint_passes_redacted_browser_report_file_to_child_verifier(self):
		commands = []
		browser_report_file = "/tmp/korea-browser/nested/report.json"

		def fake_run(command, **kwargs):
			commands.append(command)
			if command[0:2] == ["docker", "compose"]:
				return self.mod.CommandResult(
					returncode=0,
					stdout=json.dumps({
						"contract_type": "korea_demo_browser_credential_runtime_apply_v1",
						"runtime_action": "demo_credential_runtime_apply",
						"requires_runtime_apply": False,
						"credential_ready_for_browser_verifier": True,
						"human_approval_verified": True,
						"mutation_boundary": "credential_only_no_payroll_submit_approve_send_provider_call",
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
			browser_report_file=browser_report_file,
			run_command=fake_run,
		)

		self.assertTrue(report["browser_verification"]["passed"])
		self.assertIn("--report-file", commands[1])
		self.assertIn(browser_report_file, commands[1])
		self.assertEqual(report["browser_verification"]["report_file"], browser_report_file)
		self.assertNotIn("runtime-secret", json.dumps(report))

	def test_checkpoint_accepts_noisy_stdout_wrapping_final_json_payloads(self):
		def fake_run(command, **kwargs):
			if command[0:2] == ["docker", "compose"]:
				return self.mod.CommandResult(
					returncode=0,
					stdout="bench log line before json\n" + json.dumps({
						"contract_type": "korea_demo_browser_credential_runtime_apply_v1",
						"runtime_action": "demo_credential_runtime_apply",
						"requires_runtime_apply": False,
						"credential_ready_for_browser_verifier": True,
						"human_approval_verified": True,
						"mutation_boundary": "credential_only_no_payroll_submit_approve_send_provider_call",
						"requires_human_approval": True,
						"ai_role": "assistant_only",
						"safety_metadata": {"source": "credential_apply"},
					}) + "\npost-json bench notice\n",
					stderr="",
				)
			return self.mod.CommandResult(
				returncode=0,
				stdout="node startup log\n" + json.dumps({
					"contract_type": "korea_payroll_closing_browser_runtime_walkthrough_v1",
					"runtime_action": "browser_runtime_read_only",
					"requires_runtime_apply": False,
					"requires_human_approval": True,
					"ai_role": "assistant_only",
					"mutation_boundary": "read_only_no_save_submit_approve_send_provider",
					"runtime_verified": True,
					"fixture_fallback_required": False,
					"safety_metadata": {"source": "browser_verifier"},
				}) + "\npost-json browser notice\n",
				stderr="",
			)

		report = self.mod.verify_demo_browser_credential_apply(
			repo_root=self.repo_root,
			environ={"FRAPPE_BROWSER_PASSWORD": "runtime-secret"},
			human_approved=True,
			run_command=fake_run,
		)

		self.assertTrue(report["credential_apply"]["passed"])
		self.assertTrue(report["browser_verification"]["passed"])
		self.assertTrue(report["runtime_verified"])
		self.assertFalse(report["fixture_fallback_required"])
		serialized = json.dumps(report, ensure_ascii=False)
		self.assertNotIn("runtime-secret", serialized)

	def test_checkpoint_rejects_browser_positive_without_safety_metadata(self):
		def fake_run(command, **kwargs):
			if command[0:2] == ["docker", "compose"]:
				return self.mod.CommandResult(
					returncode=0,
					stdout=json.dumps({
						"contract_type": "korea_demo_browser_credential_runtime_apply_v1",
						"runtime_action": "demo_credential_runtime_apply",
						"requires_runtime_apply": False,
						"credential_ready_for_browser_verifier": True,
						"human_approval_verified": True,
						"mutation_boundary": "credential_only_no_payroll_submit_approve_send_provider_call",
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
		self.assertEqual(report["credential_apply"]["reason"], "credential apply command failed")
		self.assertFalse(report["browser_verification"]["attempted"])
		self.assertFalse(report["runtime_verified"])
		self.assertNotIn("runtime-secret", json.dumps(report))

	def test_checkpoint_reports_browser_command_failure_reason(self):
		def fake_run(command, **kwargs):
			if command[0:2] == ["docker", "compose"]:
				return self.mod.CommandResult(
					returncode=0,
					stdout=json.dumps({
						"contract_type": "korea_demo_browser_credential_runtime_apply_v1",
						"runtime_action": "demo_credential_runtime_apply",
						"requires_runtime_apply": False,
						"credential_ready_for_browser_verifier": True,
						"human_approval_verified": True,
						"mutation_boundary": "credential_only_no_payroll_submit_approve_send_provider_call",
						"requires_human_approval": True,
						"ai_role": "assistant_only",
					}),
					stderr="",
				)
			return self.mod.CommandResult(returncode=1, stdout="", stderr="browser failed")

		report = self.mod.verify_demo_browser_credential_apply(
			repo_root=self.repo_root,
			environ={"FRAPPE_BROWSER_PASSWORD": "runtime-secret"},
			human_approved=True,
			run_command=fake_run,
		)

		self.assertTrue(report["credential_apply"]["passed"])
		self.assertTrue(report["browser_verification"]["attempted"])
		self.assertFalse(report["browser_verification"]["passed"])
		self.assertEqual(report["browser_verification"]["reason"], "browser verifier command failed")
		self.assertFalse(report["runtime_verified"])
		self.assertTrue(report["fixture_fallback_required"])
		self.assertNotIn("runtime-secret", json.dumps(report))

	def test_checkpoint_rejects_credential_apply_without_safety_metadata(self):
		commands = []

		def fake_run(command, **kwargs):
			commands.append(command)
			return self.mod.CommandResult(
				returncode=0,
				stdout=json.dumps({
					"contract_type": "korea_demo_browser_credential_runtime_apply_v1",
					"runtime_action": "demo_credential_runtime_apply",
					"credential_ready_for_browser_verifier": True,
					"human_approval_verified": True,
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

		self.assertEqual(len(commands), 1)
		self.assertTrue(report["credential_apply"]["attempted"])
		self.assertFalse(report["credential_apply"]["passed"])
		self.assertEqual(report["credential_apply"]["reason"], "credential apply safety metadata invalid")
		self.assertFalse(report["browser_verification"]["attempted"])
		self.assertFalse(report["runtime_verified"])
		self.assertNotIn("runtime-secret", json.dumps(report))

	def test_cli_report_file_creates_parent_directory_and_writes_utf8_report(self):
		with tempfile.TemporaryDirectory() as temp_dir:
			report_path = pathlib.Path(temp_dir) / "nested" / "checkpoint" / "report.json"
			completed = subprocess.run(
				[
					sys.executable,
					str(SCRIPT_PATH),
					"--repo-root",
					str(self.repo_root),
					"--site",
					"hrms.localhost",
					"--company",
					"노란봉투법 데모",
					"--base-url",
					"http://127.0.0.1:8000",
					"--report-file",
					str(report_path),
				],
				cwd=self.repo_root,
				env={**os.environ, "FRAPPE_BROWSER_PASSWORD": ""},
				text=True,
				capture_output=True,
				check=False,
			)

			self.assertEqual(completed.returncode, 1)
			self.assertEqual(completed.stderr, "")
			self.assertTrue(report_path.exists())
			report = json.loads(report_path.read_text(encoding="utf-8"))
			stdout_report = json.loads(completed.stdout)
			self.assertEqual(stdout_report, report)
			self.assertEqual(report["scope"]["company_provided"], True)
			self.assertEqual(report["credential_apply"]["reason"], "FRAPPE_BROWSER_PASSWORD blank")

	def test_checkpoint_reports_empty_password_env_as_blank_not_missing(self):
		report = self.mod.verify_demo_browser_credential_apply(
			repo_root=self.repo_root,
			environ={"FRAPPE_BROWSER_PASSWORD": ""},
			human_approved=True,
			dry_run=True,
		)

		self.assertFalse(report["credential_apply"]["attempted"])
		self.assertEqual(report["credential_apply"]["reason"], "FRAPPE_BROWSER_PASSWORD blank")
		self.assertFalse(report["browser_verification"]["attempted"])
		self.assertFalse(report["runtime_verified"])
		self.assertTrue(report["fixture_fallback_required"])


if __name__ == "__main__":
	unittest.main()
