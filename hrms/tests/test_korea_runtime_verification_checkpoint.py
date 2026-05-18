#!/usr/bin/env python3
"""Direct tests for the Korea runtime verification checkpoint script."""

from __future__ import annotations

import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "verify_korea_payroll_closing_runtime.py"


def load_module():
	spec = importlib.util.spec_from_file_location("verify_korea_payroll_closing_runtime", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


class KoreaRuntimeVerificationCheckpointTest(unittest.TestCase):
	def test_dry_run_reports_read_only_runtime_checkpoint(self):
		module = load_module()

		report = module.verify_runtime_checkpoint(repo_root=REPO_ROOT, dry_run=True)

		self.assertEqual(report["contract_type"], "korea_payroll_closing_runtime_verification_v1")
		self.assertEqual(report["runtime_action"], "runtime_verification_read_only")
		self.assertFalse(report["requires_runtime_apply"])
		self.assertEqual(report["ai_role"], "assistant_only")
		self.assertEqual(report["mutation_boundary"], "read_only_no_save_submit_approve_send_provider")
		self.assertEqual(report["bench_probe"]["skipped"], True)
		self.assertEqual(report["bench_probe"]["reason"], "bench probe not requested")
		self.assertEqual(report["runtime_verified"], False)
		self.assertEqual(report["passed"], False)
		self.assertIn("runtime not verified", report["runtime_blockers"])
		self.assertIn("docker compose", report["docker_compose"]["command"])
		for command_report in (report["docker_compose"], report["bench_probe"]):
			command_text = command_report["command"].lower()
			self.assertNotIn(" save", command_text)
			self.assertNotIn("submit", command_text)
			self.assertNotIn("approve", command_text)
			self.assertNotIn("send", command_text)
			self.assertNotIn("provider", command_text)

	def test_bench_probe_command_targets_worklist_runtime_read(self):
		module = load_module()

		command = module.build_bench_worklist_probe_command(site="korea.local", company="Korea Demo Co", workplaces=["Seoul HQ"])
		joined = " ".join(command)

		self.assertEqual(command[:4], ["bench", "--site", "korea.local", "execute"])
		self.assertIn("payroll_closing_worklist_runtime_api.list_korea_payroll_closing_worklist_runtime", joined)
		self.assertIn("--kwargs", command)
		kwargs = json.loads(command[command.index("--kwargs") + 1])
		self.assertEqual(kwargs["company"], "Korea Demo Co")
		self.assertEqual(kwargs["workplaces"], ["Seoul HQ"])
		self.assertNotIn("save", joined.lower())
		self.assertNotIn("submit", joined.lower())
		self.assertNotIn("approve", joined.lower())
		self.assertNotIn("send", joined.lower())
		self.assertNotIn("provider", joined.lower())

	def test_local_docker_bench_probe_uses_container_bench_without_host_bench(self):
		module = load_module()

		command = module.build_docker_bench_worklist_probe_command(
			repo_root=REPO_ROOT,
			site="korea.local",
			company="Korea Demo Co",
			workplaces=["Seoul HQ"],
		)
		joined = " ".join(command)

		self.assertEqual(command[:6], ["docker", "compose", "-f", str(REPO_ROOT / "docker" / "docker-compose.yml"), "exec", "-T"])
		self.assertIn("frappe", command)
		self.assertIn("cd /home/frappe/frappe-bench", joined)
		self.assertIn("bench --site korea.local execute", joined)
		self.assertIn("payroll_closing_worklist_runtime_api.list_korea_payroll_closing_worklist_runtime", joined)
		self.assertIn('"company": "Korea Demo Co"', joined)
		self.assertIn('"workplaces": ["Seoul HQ"]', joined)
		self.assertNotIn(" save", joined.lower())
		self.assertNotIn("submit", joined.lower())
		self.assertNotIn("approve", joined.lower())
		self.assertNotIn("send", joined.lower())
		self.assertNotIn("provider", joined.lower())

	def test_local_docker_runtime_source_probe_reports_mounted_workspace_alignment(self):
		module = load_module()

		command = module.build_docker_runtime_source_probe_command(repo_root=REPO_ROOT)
		joined = " ".join(command)

		self.assertEqual(command[:6], ["docker", "compose", "-f", str(REPO_ROOT / "docker" / "docker-compose.yml"), "exec", "-T"])
		self.assertIn("/workspace/hrms-source", joined)
		self.assertIn("/home/frappe/frappe-bench/apps/hrms", joined)
		self.assertIn("safe.directory", joined)
		self.assertNotIn("config --global", joined)
		self.assertNotIn("--add safe.directory", joined)
		self.assertNotIn(" save", joined.lower())
		self.assertNotIn("submit", joined.lower())
		self.assertNotIn("approve", joined.lower())
		self.assertNotIn("send", joined.lower())
		self.assertNotIn("provider", joined.lower())

	def test_stale_local_docker_runtime_source_blocks_positive_row_closeout(self):
		module = load_module()

		class DockerCompleted:
			returncode = 0
			stdout = json.dumps([{"Service": "frappe", "State": "running", "Health": "healthy"}])
			stderr = ""

		class SourceCompleted:
			returncode = 0
			stdout = json.dumps({"mounted_source_head": "newer123", "runtime_app_head": "older456"})
			stderr = ""

		class BenchCompleted:
			returncode = 0
			stdout = json.dumps({"contract_type": "korea_payroll_closing_worklist_runtime_api_v1", "items": [{"name": "DRAFT-1"}]})
			stderr = ""

		def fake_run(command, **kwargs):
			if command[:2] == ["docker", "compose"] and "ps" in command:
				return DockerCompleted()
			if command[:2] == ["docker", "compose"] and "runtime_app_head" in command[-1]:
				return SourceCompleted()
			return BenchCompleted()

		with patch.object(module.shutil, "which", return_value="/usr/bin/tool"), patch.object(module.subprocess, "run", side_effect=fake_run):
			report = module.verify_runtime_checkpoint(repo_root=REPO_ROOT, include_bench=True, site="hrms.localhost")

		self.assertFalse(report["runtime_source"]["source_matches_mounted_workspace"])
		self.assertTrue(report["runtime_closeout"]["positive_runtime_rows_verified"])
		self.assertFalse(report["command_checks_passed"])
		self.assertFalse(report["runtime_verified"])
		self.assertFalse(report["passed"])
		self.assertIn("runtime app source is not aligned with mounted workspace", report["runtime_blockers"])
		self.assertIn("refresh Docker Bench HRMS app checkout from mounted workspace", report["runtime_closeout"]["next_actions"])
		self.assertNotIn("newer123", json.dumps(report, ensure_ascii=False))
		self.assertNotIn("older456", json.dumps(report, ensure_ascii=False))

	def test_failed_local_docker_runtime_source_probe_blocks_positive_row_closeout(self):
		module = load_module()

		class DockerCompleted:
			returncode = 0
			stdout = json.dumps([{"Service": "frappe", "State": "running", "Health": "healthy"}])
			stderr = ""

		class SourceFailed:
			returncode = 128
			stdout = ""
			stderr = "fatal: not a git repository"

		class BenchCompleted:
			returncode = 0
			stdout = json.dumps({"contract_type": "korea_payroll_closing_worklist_runtime_api_v1", "items": [{"name": "DRAFT-1"}]})
			stderr = ""

		def fake_run(command, **kwargs):
			if command[:2] == ["docker", "compose"] and "ps" in command:
				return DockerCompleted()
			if command[:2] == ["docker", "compose"] and "runtime_app_head" in command[-1]:
				return SourceFailed()
			return BenchCompleted()

		with patch.object(module.shutil, "which", return_value="/usr/bin/tool"), patch.object(module.subprocess, "run", side_effect=fake_run):
			report = module.verify_runtime_checkpoint(repo_root=REPO_ROOT, include_bench=True, site="hrms.localhost")

		self.assertIsNone(report["runtime_source"].get("source_matches_mounted_workspace"))
		self.assertTrue(report["runtime_closeout"]["positive_runtime_rows_verified"])
		self.assertFalse(report["command_checks_passed"])
		self.assertFalse(report["runtime_verified"])
		self.assertFalse(report["passed"])
		self.assertIn("runtime app source alignment not verified", report["runtime_blockers"])
		self.assertIn("rerun or inspect Docker Bench HRMS source alignment probe", report["runtime_closeout"]["next_actions"])

	def test_local_docker_handoff_does_not_require_host_bench_executable(self):
		module = load_module()

		class DockerCompleted:
			returncode = 0
			stdout = json.dumps([{"Service": "frappe", "State": "running", "Health": "healthy"}])
			stderr = ""

		class SourceCompleted:
			returncode = 0
			stdout = json.dumps({"mounted_source_head": "same123", "runtime_app_head": "same123"})
			stderr = ""

		class BenchCompleted:
			returncode = 0
			stdout = json.dumps({"message": {"contract_type": "korea_payroll_closing_worklist_runtime_api_v1", "items": [{"name": "DRAFT-1"}]}})
			stderr = ""

		commands = []

		def fake_which(command):
			return "/usr/bin/docker" if command == "docker" else None

		def fake_run(command, **kwargs):
			commands.append(command)
			if command[:2] == ["docker", "compose"] and "ps" in command:
				return DockerCompleted()
			if command[:2] == ["docker", "compose"] and "runtime_app_head" in command[-1]:
				return SourceCompleted()
			return BenchCompleted()

		handoff = {
			"contract_type": "korea_payroll_closing_runtime_handoff_v1",
			"runtime_kind": "local_docker_compose_bench",
			"site": "hrms.localhost",
			"company": "Sensitive Company",
		}
		with patch.object(module.shutil, "which", side_effect=fake_which), patch.object(module.subprocess, "run", side_effect=fake_run):
			report = module.verify_runtime_checkpoint(repo_root=REPO_ROOT, runtime_handoff=handoff)

		self.assertTrue(report["passed"])
		self.assertTrue(report["runtime_verified"])
		self.assertTrue(report["runtime_closeout"]["positive_runtime_rows_verified"])
		self.assertEqual(report["runtime_ownership"]["authoritative_runtime"], "local_docker_compose_bench")
		self.assertTrue(any(command[:6] == ["docker", "compose", "-f", str(REPO_ROOT / "docker" / "docker-compose.yml"), "exec", "-T"] for command in commands))
		self.assertNotIn("Sensitive Company", json.dumps(report, ensure_ascii=False))
		self.assertNotIn("DRAFT-1", json.dumps(report, ensure_ascii=False))

	def test_include_bench_requires_site(self):
		module = load_module()

		with self.assertRaisesRegex(ValueError, "site is required when include_bench is true"):
			module.verify_runtime_checkpoint(repo_root=REPO_ROOT, include_bench=True, site=None, dry_run=True)

	def test_report_file_writes_json_artifact(self):
		module = load_module()

		with tempfile.TemporaryDirectory() as tmpdir:
			report_path = pathlib.Path(tmpdir) / "runtime-report.json"
			exit_code = module.main(["--repo-root", str(REPO_ROOT), "--dry-run", "--report-file", str(report_path)])

			self.assertEqual(exit_code, 1)
			written = json.loads(report_path.read_text(encoding="utf-8"))
			self.assertEqual(written["contract_type"], "korea_payroll_closing_runtime_verification_v1")
			self.assertEqual(written["docker_compose"]["skipped"], True)

	def test_missing_docker_is_reported_without_crashing(self):
		module = load_module()

		with patch.object(module.shutil, "which", return_value=None):
			report = module.verify_runtime_checkpoint(repo_root=REPO_ROOT)

		self.assertEqual(report["docker_compose"]["skipped"], True)
		self.assertEqual(report["docker_compose"]["reason"], "docker executable not found")
		self.assertEqual(report["runtime_verified"], False)
		self.assertEqual(report["passed"], False)

	def test_bench_probe_output_is_redacted_from_report(self):
		module = load_module()

		class Completed:
			returncode = 0
			stdout = '{"employee_name":"홍길동","contract_type":"korea_payroll_closing_worklist_runtime_api_v1"}'
			stderr = "Traceback payload employee_name=홍길동"

		with patch.object(module.shutil, "which", return_value="/usr/bin/tool"), patch.object(module.subprocess, "run", return_value=Completed()):
			report = module.verify_runtime_checkpoint(repo_root=REPO_ROOT, include_bench=True, site="korea.local")

		bench_probe = report["bench_probe"]
		self.assertNotIn("stdout_tail", bench_probe)
		self.assertNotIn("stderr_tail", bench_probe)
		self.assertEqual(bench_probe["stdout_present"], True)
		self.assertNotIn("홍길동", json.dumps(report, ensure_ascii=False))

	def test_empty_docker_compose_json_does_not_verify_runtime(self):
		module = load_module()

		class Completed:
			returncode = 0
			stdout = "[]\n"
			stderr = ""

		with patch.object(module.shutil, "which", return_value="/usr/bin/docker"), patch.object(
			module.subprocess, "run", return_value=Completed()
		):
			report = module.verify_runtime_checkpoint(repo_root=REPO_ROOT)

		self.assertEqual(report["docker_compose"]["runtime_available"], False)
		self.assertEqual(report["runtime_verified"], False)
		self.assertEqual(report["passed"], False)

	def test_stopped_docker_compose_service_does_not_verify_runtime(self):
		module = load_module()

		class Completed:
			returncode = 0
			stdout = json.dumps([{"Service": "frappe", "State": "exited", "Health": ""}])
			stderr = ""

		with patch.object(module.shutil, "which", return_value="/usr/bin/docker"), patch.object(
			module.subprocess, "run", return_value=Completed()
		):
			report = module.verify_runtime_checkpoint(repo_root=REPO_ROOT)

		self.assertEqual(report["docker_compose"]["runtime_available"], False)
		self.assertIn("docker compose runtime not running", report["runtime_blockers"])

	def test_running_docker_compose_service_without_bench_does_not_verify_runtime_rows(self):
		module = load_module()

		class Completed:
			returncode = 0
			stdout = json.dumps([{"Service": "frappe", "State": "running", "Health": "healthy"}])
			stderr = ""

		with patch.object(module.shutil, "which", return_value="/usr/bin/docker"), patch.object(
			module.subprocess, "run", return_value=Completed()
		):
			report = module.verify_runtime_checkpoint(repo_root=REPO_ROOT)

		self.assertEqual(report["docker_compose"]["runtime_available"], True)
		self.assertEqual(report["runtime_verified"], False)
		self.assertIn("positive runtime rows not verified", report["runtime_blockers"])
		self.assertEqual(report["passed"], False)
		self.assertEqual(report["runtime_closeout"]["gate_6_blockers_resolved"], False)
		self.assertIn("run bench read-only worklist probe with --include-bench --site", report["runtime_closeout"]["next_actions"])

	def test_running_non_frappe_service_does_not_verify_runtime(self):
		module = load_module()

		class Completed:
			returncode = 0
			stdout = json.dumps([{"Service": "mariadb", "State": "running", "Health": "healthy"}])
			stderr = ""

		with patch.object(module.shutil, "which", return_value="/usr/bin/docker"), patch.object(
			module.subprocess, "run", return_value=Completed()
		):
			report = module.verify_runtime_checkpoint(repo_root=REPO_ROOT)

		self.assertEqual(report["docker_compose"]["runtime_available"], False)
		self.assertEqual(report["runtime_verified"], False)
		self.assertEqual(report["passed"], False)

	def test_bench_probe_command_and_report_scope_are_redacted(self):
		module = load_module()

		class Completed:
			returncode = 0
			stdout = json.dumps([{"Service": "frappe", "State": "running"}])
			stderr = ""

		with patch.object(module.shutil, "which", return_value="/usr/bin/tool"), patch.object(
			module.subprocess, "run", return_value=Completed()
		):
			report = module.verify_runtime_checkpoint(
				repo_root=REPO_ROOT,
				include_bench=True,
				site="korea.local",
				company="Sensitive Company",
				workplaces=["Sensitive Workplace"],
			)

		report_json = json.dumps(report, ensure_ascii=False)
		self.assertNotIn("Sensitive Company", report_json)
		self.assertNotIn("Sensitive Workplace", report_json)
		self.assertNotIn("korea.local", report_json)
		self.assertIn("bash -lc '[redacted]'", report["bench_probe"]["command"])
		self.assertNotIn("--kwargs", report["bench_probe"]["command"])
		self.assertEqual(report["scope"], {"company_provided": True, "workplace_count": 1, "site_provided": True})

	def test_skipped_command_checks_are_not_reported_as_passed(self):
		module = load_module()

		with patch.object(module.shutil, "which", return_value=None):
			report = module.verify_runtime_checkpoint(repo_root=REPO_ROOT)

		self.assertEqual(report["docker_compose"]["skipped"], True)
		self.assertEqual(report["command_checks_passed"], False)

	def test_docker_compose_report_includes_redacted_service_summary(self):
		module = load_module()

		class Completed:
			returncode = 0
			stdout = json.dumps([
				{"Service": "frappe", "State": "running", "Health": "healthy"},
				{"Service": "mariadb", "State": "running", "Health": "healthy"},
				{"Service": "redis", "State": "exited", "Health": ""},
			])
			stderr = ""

		with patch.object(module.shutil, "which", return_value="/usr/bin/docker"), patch.object(
			module.subprocess, "run", return_value=Completed()
		):
			report = module.verify_runtime_checkpoint(repo_root=REPO_ROOT)

		self.assertEqual(report["docker_compose"]["service_count"], 3)
		self.assertEqual(report["docker_compose"]["running_services"], ["frappe", "mariadb"])
		self.assertNotIn("stdout_tail", report["docker_compose"])
		self.assertEqual(report["runtime_closeout"]["docker_runtime_running"], True)

	def test_runtime_closeout_keeps_fixture_fallback_when_bench_is_unavailable(self):
		module = load_module()

		class Completed:
			returncode = 0
			stdout = "[]\n"
			stderr = "compose warning only"

		def fake_which(command):
			return "/usr/bin/docker" if command == "docker" else None

		with patch.object(module.shutil, "which", side_effect=fake_which), patch.object(
			module.subprocess, "run", return_value=Completed()
		):
			report = module.verify_runtime_checkpoint(repo_root=REPO_ROOT, include_bench=True, site="hrms.localhost")

		closeout = report["runtime_closeout"]
		self.assertEqual(closeout["gate_6_blockers_resolved"], False)
		self.assertEqual(closeout["docker_runtime_running"], False)
		self.assertEqual(closeout["bench_executable_available"], True)
		self.assertEqual(closeout["positive_runtime_rows_verified"], False)
		self.assertEqual(closeout["fixture_fallback_required"], True)
		self.assertEqual(report["passed"], False)
		self.assertIn("start Docker Compose Frappe runtime", closeout["next_actions"])
		self.assertIn("verify positive Korea Payroll Closing Draft rows through the read-only worklist path", closeout["next_actions"])
		self.assertNotIn("bench executable not found", report["runtime_blockers"])

	def test_bench_probe_failure_does_not_report_bench_executable_unavailable(self):
		module = load_module()

		class DockerCompleted:
			returncode = 0
			stdout = json.dumps([{"Service": "frappe", "State": "running", "Health": "healthy"}])
			stderr = ""

		class BenchCompleted:
			returncode = 1
			stdout = ""
			stderr = "bench validation failed"

		def fake_run(command, **kwargs):
			return DockerCompleted() if command[:2] == ["docker", "compose"] and "ps" in command else BenchCompleted()

		with patch.object(module.shutil, "which", return_value="/usr/bin/tool"), patch.object(module.subprocess, "run", side_effect=fake_run):
			report = module.verify_runtime_checkpoint(repo_root=REPO_ROOT, include_bench=True, site="hrms.localhost")

		closeout = report["runtime_closeout"]
		self.assertEqual(closeout["bench_executable_available"], True)
		self.assertNotIn("install or expose bench executable", closeout["next_actions"])
		self.assertIn("inspect failed read-only bench worklist probe", closeout["next_actions"])
		self.assertIn("bench worklist runtime read failed", report["runtime_blockers"])
		self.assertEqual(report["passed"], False)

	def test_runtime_ownership_requires_operator_runtime_when_local_docker_and_bench_are_absent(self):
		module = load_module()

		with patch.object(module.shutil, "which", return_value=None):
			report = module.verify_runtime_checkpoint(repo_root=REPO_ROOT, include_bench=True, site="hrms.localhost")

		ownership = report["runtime_ownership"]
		self.assertEqual(ownership["contract_type"], "korea_payroll_closing_runtime_ownership_v1")
		self.assertEqual(ownership["runtime_action"], "runtime_ownership_decision_read_only")
		self.assertFalse(ownership["requires_runtime_apply"])
		self.assertEqual(ownership["ai_role"], "assistant_only")
		self.assertEqual(ownership["authoritative_runtime"], "operator_provided_runtime_required")
		self.assertEqual(ownership["decision_status"], "blocked")
		self.assertIn("local Docker Compose Frappe runtime is not running", ownership["evidence"])
		self.assertIn("bench executable is not available in this cron environment", ownership["evidence"])
		self.assertIn("provide or expose an authoritative Bench/Frappe runtime", ownership["next_actions"])
		self.assertTrue(report["fixture_fallback_required_until_positive_runtime_rows"])

	def test_runtime_ownership_uses_local_docker_when_compose_and_bench_rows_are_positive(self):
		module = load_module()

		class DockerCompleted:
			returncode = 0
			stdout = json.dumps([{"Service": "frappe", "State": "running", "Health": "healthy"}])
			stderr = ""

		class SourceCompleted:
			returncode = 0
			stdout = json.dumps({"mounted_source_head": "same123", "runtime_app_head": "same123"})
			stderr = ""

		class BenchCompleted:
			returncode = 0
			stdout = json.dumps({"contract_type": "korea_payroll_closing_worklist_runtime_api_v1", "items": [{"name": "DRAFT-1"}]})
			stderr = ""

		def fake_run(command, **kwargs):
			if command[:2] == ["docker", "compose"] and "ps" in command:
				return DockerCompleted()
			if command[:2] == ["docker", "compose"] and "runtime_app_head" in command[-1]:
				return SourceCompleted()
			return BenchCompleted()

		with patch.object(module.shutil, "which", return_value="/usr/bin/tool"), patch.object(module.subprocess, "run", side_effect=fake_run):
			report = module.verify_runtime_checkpoint(repo_root=REPO_ROOT, include_bench=True, site="hrms.localhost")

		ownership = report["runtime_ownership"]
		self.assertEqual(ownership["authoritative_runtime"], "local_docker_compose_bench")
		self.assertEqual(ownership["decision_status"], "verified")
		self.assertIn("local Docker Compose Frappe service is running", ownership["evidence"])
		self.assertIn("read-only bench worklist probe returned positive scoped rows", ownership["evidence"])
		self.assertEqual(ownership["next_actions"], [])

	def test_positive_bench_worklist_rows_can_close_runtime_gate(self):
		module = load_module()

		class DockerCompleted:
			returncode = 0
			stdout = json.dumps([{"Service": "frappe", "State": "running", "Health": "healthy"}])
			stderr = ""

		class SourceCompleted:
			returncode = 0
			stdout = json.dumps({"mounted_source_head": "same123", "runtime_app_head": "same123"})
			stderr = ""

		class BenchCompleted:
			returncode = 0
			stdout = json.dumps({"contract_type": "korea_payroll_closing_worklist_runtime_api_v1", "items": [{"name": "DRAFT-1"}]})
			stderr = ""

		def fake_run(command, **kwargs):
			if command[:2] == ["docker", "compose"] and "ps" in command:
				return DockerCompleted()
			if command[:2] == ["docker", "compose"] and "runtime_app_head" in command[-1]:
				return SourceCompleted()
			return BenchCompleted()

		with patch.object(module.shutil, "which", return_value="/usr/bin/tool"), patch.object(module.subprocess, "run", side_effect=fake_run):
			report = module.verify_runtime_checkpoint(repo_root=REPO_ROOT, include_bench=True, site="hrms.localhost")

		closeout = report["runtime_closeout"]
		self.assertEqual(closeout["gate_6_blockers_resolved"], True)
		self.assertEqual(closeout["positive_runtime_rows_verified"], True)
		self.assertEqual(closeout["fixture_fallback_required"], False)
		self.assertEqual(report["fixture_fallback_required_until_positive_runtime_rows"], False)
		self.assertEqual(report["passed"], True)
		self.assertNotIn("DRAFT-1", json.dumps(report, ensure_ascii=False))

	def test_malformed_bench_items_do_not_close_runtime_gate(self):
		module = load_module()

		class DockerCompleted:
			returncode = 0
			stdout = json.dumps([{"Service": "frappe", "State": "running", "Health": "healthy"}])
			stderr = ""

		class BenchCompleted:
			returncode = 0
			stdout = json.dumps({"contract_type": "korea_payroll_closing_worklist_runtime_api_v1", "items": [None, "not-a-row"]})
			stderr = ""

		def fake_run(command, **kwargs):
			return DockerCompleted() if command[:2] == ["docker", "compose"] and "ps" in command else BenchCompleted()

		with patch.object(module.shutil, "which", return_value="/usr/bin/tool"), patch.object(module.subprocess, "run", side_effect=fake_run):
			report = module.verify_runtime_checkpoint(repo_root=REPO_ROOT, include_bench=True, site="hrms.localhost")

		self.assertEqual(report["runtime_closeout"]["positive_runtime_rows_verified"], False)
		self.assertEqual(report["runtime_closeout"]["gate_6_blockers_resolved"], False)
		self.assertEqual(report["passed"], False)

	def test_operator_runtime_handoff_can_verify_positive_rows_without_local_docker(self):
		module = load_module()

		class DockerCompleted:
			returncode = 0
			stdout = "[]\n"
			stderr = ""

		class BenchCompleted:
			returncode = 0
			stdout = json.dumps({"message": {"contract_type": "korea_payroll_closing_worklist_runtime_api_v1", "items": [{"name": "DRAFT-1"}]}})
			stderr = ""

		def fake_run(command, **kwargs):
			return DockerCompleted() if command[:2] == ["docker", "compose"] and "ps" in command else BenchCompleted()

		handoff = {
			"contract_type": "korea_payroll_closing_runtime_handoff_v1",
			"runtime_kind": "operator_provided_bench",
			"site": "operator.local",
			"company": "Sensitive Company",
			"workplaces": ["Sensitive Workplace"],
		}
		with patch.object(module.shutil, "which", return_value="/usr/bin/tool"), patch.object(module.subprocess, "run", side_effect=fake_run):
			report = module.verify_runtime_checkpoint(repo_root=REPO_ROOT, runtime_handoff=handoff)

		self.assertTrue(report["passed"])
		self.assertTrue(report["command_checks_passed"])
		self.assertTrue(report["runtime_verified"])
		self.assertFalse(report["fixture_fallback_required_until_positive_runtime_rows"])
		self.assertEqual(report["runtime_handoff"]["runtime_kind"], "operator_provided_bench")
		self.assertEqual(report["runtime_ownership"]["authoritative_runtime"], "operator_provided_bench")
		self.assertEqual(report["runtime_ownership"]["decision_status"], "verified")
		report_json = json.dumps(report, ensure_ascii=False)
		self.assertNotIn("Sensitive Company", report_json)
		self.assertNotIn("Sensitive Workplace", report_json)
		self.assertNotIn("operator.local", report_json)
		self.assertNotIn("DRAFT-1", report_json)

	def test_operator_runtime_handoff_command_checks_do_not_require_local_docker(self):
		module = load_module()

		class BenchCompleted:
			returncode = 0
			stdout = json.dumps({"contract_type": "korea_payroll_closing_worklist_runtime_api_v1", "items": [{"name": "DRAFT-1"}]})
			stderr = ""

		def fake_which(command):
			return None if command == "docker" else "/usr/bin/bench"

		handoff = {
			"contract_type": "korea_payroll_closing_runtime_handoff_v1",
			"runtime_kind": "operator_provided_bench",
			"site": "operator.local",
		}
		with patch.object(module.shutil, "which", side_effect=fake_which), patch.object(module.subprocess, "run", return_value=BenchCompleted()):
			report = module.verify_runtime_checkpoint(repo_root=REPO_ROOT, runtime_handoff=handoff)

		self.assertEqual(report["docker_compose"]["skipped"], True)
		self.assertEqual(report["docker_compose"]["reason"], "docker executable not found")
		self.assertEqual(report["runtime_closeout"]["docker_runtime_required"], False)
		self.assertTrue(report["command_checks_passed"])
		self.assertTrue(report["passed"])
		self.assertEqual(report["runtime_blockers"], [])

	def test_runtime_handoff_rejects_malformed_contract_before_probe(self):
		module = load_module()

		with self.assertRaisesRegex(ValueError, "runtime_handoff.contract_type must be korea_payroll_closing_runtime_handoff_v1"):
			module.verify_runtime_checkpoint(
				repo_root=REPO_ROOT,
				runtime_handoff={"contract_type": "evil", "runtime_kind": "operator_provided_bench", "site": "operator.local"},
			)

	def test_runtime_handoff_file_drives_cli_probe_without_exposing_scope(self):
		module = load_module()

		class DockerCompleted:
			returncode = 0
			stdout = "[]\n"
			stderr = ""

		class BenchCompleted:
			returncode = 0
			stdout = json.dumps({"contract_type": "korea_payroll_closing_worklist_runtime_api_v1", "items": [{"name": "DRAFT-1"}]})
			stderr = ""

		def fake_run(command, **kwargs):
			return DockerCompleted() if command[:2] == ["docker", "compose"] and "ps" in command else BenchCompleted()

		with tempfile.TemporaryDirectory() as tmpdir:
			handoff_path = pathlib.Path(tmpdir) / "handoff.json"
			report_path = pathlib.Path(tmpdir) / "report.json"
			handoff_path.write_text(
				json.dumps({
					"contract_type": "korea_payroll_closing_runtime_handoff_v1",
					"runtime_kind": "operator_provided_bench",
					"site": "operator.local",
					"company": "Sensitive Company",
				}, ensure_ascii=False),
				encoding="utf-8",
			)
			with patch.object(module.shutil, "which", return_value="/usr/bin/tool"), patch.object(
				module.subprocess, "run", side_effect=fake_run
			):
				exit_code = module.main([
					"--repo-root",
					str(REPO_ROOT),
					"--runtime-handoff-file",
					str(handoff_path),
					"--report-file",
					str(report_path),
				])

			self.assertEqual(exit_code, 0)
			written = json.loads(report_path.read_text(encoding="utf-8"))
			self.assertEqual(written["runtime_handoff"]["runtime_kind"], "operator_provided_bench")
			self.assertTrue(written["passed"])
			self.assertNotIn("Sensitive Company", json.dumps(written, ensure_ascii=False))


if __name__ == "__main__":
	unittest.main()
