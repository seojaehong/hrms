#!/usr/bin/env python3
"""Cron-safe Korea regional smoke harness.

Runs the framework-free Korea productization tests without importing the HRMS
package, then optionally runs a bench smoke command when a bench runtime is
available. The optional bench leg is intentionally skipped by default in
no-runtime workspaces.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import shlex
import shutil
import subprocess
import sys
from typing import Any

_EXCLUDED_DIRECT_TEST_FILENAMES = {
	# The harness test validates this script; running it from the harness itself
	# would add noisy recursion without increasing regional contract coverage.
	"test_korea_regional_smoke_harness.py",
}


def korea_direct_test_targets(repo_root: pathlib.Path) -> list[str]:
	"""Return discovered Korea direct-run test files as repo-relative paths."""

	root = pathlib.Path(repo_root)
	tests_dir = root / "hrms" / "tests"
	if not tests_dir.exists():
		return []
	targets = []
	for path in tests_dir.glob("test_korea*.py"):
		if path.name in _EXCLUDED_DIRECT_TEST_FILENAMES:
			continue
		targets.append(path.relative_to(root).as_posix())
	return sorted(targets)


def build_direct_test_commands(repo_root: pathlib.Path) -> list[list[str]]:
	"""Build no-bench commands that execute test files directly.

	Using file execution avoids importing ``hrms`` as a package, which would require
	Frappe in cron/no-bench environments.
	"""

	return [[sys.executable, target] for target in korea_direct_test_targets(repo_root)]


def build_optional_bench_command(*, site: str) -> list[str]:
	"""Build the future bench smoke command without assuming bench exists."""

	return [
		"bench",
		"--site",
		site,
		"run-tests",
		"--app",
		"hrms",
		"--module",
		"hrms.tests.test_korea_statutory_payroll",
	]


def run_command(command: list[str], *, dry_run: bool = False, cwd: pathlib.Path | None = None) -> dict[str, Any]:
	"""Run a command and return a report-safe result object."""

	command_text = shlex.join(command)
	if dry_run:
		return {"command": command_text, "skipped": True, "returncode": 0}

	completed = subprocess.run(command, cwd=str(cwd) if cwd else None, text=True, capture_output=True, check=False)
	return {
		"command": command_text,
		"returncode": completed.returncode,
		"stdout_tail": _tail(completed.stdout),
		"stderr_tail": _tail(completed.stderr),
	}


def run_smoke(*, repo_root: pathlib.Path, include_bench: bool = False, site: str | None = None, dry_run: bool = False) -> dict[str, Any]:
	"""Run direct Korea tests and optionally a bench smoke leg."""

	repo_root = pathlib.Path(repo_root).resolve()
	direct_commands = build_direct_test_commands(repo_root)
	if not direct_commands:
		direct_results = [{"command": "korea direct tests", "reason": "no Korea direct test targets found", "returncode": 1}]
	else:
		direct_results = [run_command(command, dry_run=dry_run, cwd=repo_root) for command in direct_commands]
	bench_result: dict[str, Any] | None = None
	if include_bench:
		if not site:
			raise ValueError("--site is required when --include-bench is used")
		if shutil.which("bench") is None and not dry_run:
			bench_result = {"command": "bench", "skipped": True, "reason": "bench executable not found", "returncode": 0}
		else:
			bench_result = run_command(build_optional_bench_command(site=site), dry_run=dry_run, cwd=repo_root)

	failed = [result for result in direct_results if result.get("returncode") != 0]
	if bench_result and bench_result.get("returncode") != 0:
		failed.append(bench_result)
	return {
		"contract_type": "korea_regional_smoke_harness_v1",
		"repo_root": str(repo_root),
		"python_executable": sys.executable,
		"direct_target_count": len(direct_commands),
		"direct_results": direct_results,
		"bench_result": bench_result,
		"passed": not failed,
		"failed_count": len(failed),
	}


def _tail(text: str, *, max_lines: int = 40) -> str:
	lines = text.splitlines()
	return "\n".join(lines[-max_lines:])


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(description="Run Korea regional direct smoke tests and optional bench smoke.")
	parser.add_argument("--repo-root", default=str(pathlib.Path(__file__).resolve().parents[1]))
	parser.add_argument("--include-bench", action="store_true")
	parser.add_argument("--site")
	parser.add_argument("--dry-run", action="store_true")
	parser.add_argument("--report-file", help="Optional path to write the JSON smoke report for CI/cron artifacts.")
	args = parser.parse_args(argv)

	result = run_smoke(
		repo_root=pathlib.Path(args.repo_root),
		include_bench=args.include_bench,
		site=args.site,
		dry_run=args.dry_run,
	)
	json_report = json.dumps(result, ensure_ascii=False, indent=2)
	print(json_report)
	if args.report_file:
		report_path = pathlib.Path(args.report_file)
		report_path.parent.mkdir(parents=True, exist_ok=True)
		report_path.write_text(json_report + "\n", encoding="utf-8")
	return 0 if result["passed"] else 1


if __name__ == "__main__":
	raise SystemExit(main())
