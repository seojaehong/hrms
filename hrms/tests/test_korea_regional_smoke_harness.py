#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "run_korea_regional_smoke.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_regional_smoke_harness", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


class TestKoreaRegionalSmokeHarness(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()

	def test_direct_test_targets_cover_regional_productization_contracts(self):
		targets = self.mod.korea_direct_test_targets(ROOT)

		expected_targets = {
			"hrms/tests/test_korea_admin_dashboard.py",
			"hrms/tests/test_korea_annual_leave.py",
			"hrms/tests/test_korea_approval_inbox.py",
			"hrms/tests/test_korea_approval_inbox_api.py",
			"hrms/tests/test_korea_attendance_summary.py",
			"hrms/tests/test_korea_closing_center.py",
			"hrms/tests/test_korea_compliance_checklist.py",
			"hrms/tests/test_korea_compliance_diagnosis_api.py",
			"hrms/tests/test_korea_employment_contract.py",
			"hrms/tests/test_korea_expense_settlement.py",
			"hrms/tests/test_korea_hrms_profiles.py",
			"hrms/tests/test_korea_kakao_notification.py",
			"hrms/tests/test_korea_leave_allocation_adapter.py",
			"hrms/tests/test_korea_mobile_ess_mss_contracts.py",
			"hrms/tests/test_korea_mobile_ess_mss_api.py",
			"hrms/tests/test_korea_payroll_salary_slip_adapter.py",
			"hrms/tests/test_korea_payroll_salary_slip_api.py",
			"hrms/tests/test_korea_payroll_verification_provider.py",
			"hrms/tests/test_korea_payslip.py",
			"hrms/tests/test_korea_statutory_payroll.py",
		}
		self.assertTrue(expected_targets.issubset(set(targets)), set(expected_targets).difference(targets))
		self.assertEqual(targets, sorted(targets))

	def test_builds_direct_and_optional_bench_commands_without_requiring_bench(self):
		direct = self.mod.build_direct_test_commands(ROOT)
		bench = self.mod.build_optional_bench_command(site="test.localhost")

		self.assertIn(["python3", "hrms/tests/test_korea_closing_center.py"], direct)
		self.assertIn(["python3", "hrms/tests/test_korea_mobile_ess_mss_contracts.py"], direct)
		self.assertIn(["python3", "hrms/tests/test_korea_mobile_ess_mss_api.py"], direct)
		self.assertTrue(all(command[0] == "python3" for command in direct))
		self.assertEqual(
			bench,
			[
				"bench",
				"--site",
				"test.localhost",
				"run-tests",
				"--app",
				"hrms",
				"--module",
				"hrms.tests.test_korea_statutory_payroll",
			],
		)

	def test_run_smoke_fails_when_repo_root_has_no_direct_targets(self):
		missing_root = ROOT / "does-not-exist"

		result = self.mod.run_smoke(repo_root=missing_root, dry_run=True)

		self.assertFalse(result["passed"])
		self.assertEqual(result["failed_count"], 1)
		self.assertEqual(result["direct_results"][0]["reason"], "no Korea direct test targets found")

	def test_run_smoke_dry_run_includes_mobile_ess_mss_api_direct_result(self):
		result = self.mod.run_smoke(repo_root=ROOT, dry_run=True)

		commands = [row["command"] for row in result["direct_results"]]
		self.assertTrue(result["passed"])
		self.assertIn("python3 hrms/tests/test_korea_mobile_ess_mss_api.py", commands)

	def test_run_command_supports_dry_run_for_cron_safe_reporting(self):
		result = self.mod.run_command(["python3", "--version"], dry_run=True)

		self.assertEqual(result, {"command": "python3 --version", "skipped": True, "returncode": 0})


if __name__ == "__main__":
	unittest.main()
