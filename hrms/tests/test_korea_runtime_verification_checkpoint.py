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

	def test_running_docker_compose_service_can_verify_runtime_without_bench(self):
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
		self.assertEqual(report["runtime_verified"], True)
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
		self.assertIn("--site '[redacted]'", report["bench_probe"]["command"])
		self.assertIn("--kwargs '[redacted]'", report["bench_probe"]["command"])
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
		self.assertEqual(closeout["bench_executable_available"], False)
		self.assertEqual(closeout["positive_runtime_rows_verified"], False)
		self.assertEqual(closeout["fixture_fallback_required"], True)
		self.assertEqual(report["passed"], False)
		self.assertIn("start Docker Compose Frappe runtime", closeout["next_actions"])
		self.assertIn("install or expose bench executable", closeout["next_actions"])
		self.assertIn("bench executable not found", report["runtime_blockers"])

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
			return DockerCompleted() if command[0] == "docker" else BenchCompleted()

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

		class BenchCompleted:
			returncode = 0
			stdout = json.dumps({"contract_type": "korea_payroll_closing_worklist_runtime_api_v1", "items": [{"name": "DRAFT-1"}]})
			stderr = ""

		def fake_run(command, **kwargs):
			return DockerCompleted() if command[0] == "docker" else BenchCompleted()

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

		class BenchCompleted:
			returncode = 0
			stdout = json.dumps({"contract_type": "korea_payroll_closing_worklist_runtime_api_v1", "items": [{"name": "DRAFT-1"}]})
			stderr = ""

		def fake_run(command, **kwargs):
			return DockerCompleted() if command[0] == "docker" else BenchCompleted()

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
			return DockerCompleted() if command[0] == "docker" else BenchCompleted()

		with patch.object(module.shutil, "which", return_value="/usr/bin/tool"), patch.object(module.subprocess, "run", side_effect=fake_run):
			report = module.verify_runtime_checkpoint(repo_root=REPO_ROOT, include_bench=True, site="hrms.localhost")

		self.assertEqual(report["runtime_closeout"]["positive_runtime_rows_verified"], False)
		self.assertEqual(report["runtime_closeout"]["gate_6_blockers_resolved"], False)
		self.assertEqual(report["passed"], False)


if __name__ == "__main__":
	unittest.main()
