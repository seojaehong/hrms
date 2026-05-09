#!/usr/bin/env python3
"""Korea payroll closing runtime/bench verification checkpoint.

This script is intentionally read-only at the HRMS/Frappe business-data layer. It
records whether Docker/Bench runtime appears available and, only when explicitly
requested, probes the Frappe-facing payroll closing worklist read API. It does
not save, submit, approve, send, call providers, or create payroll documents.
The optional ``--report-file`` writes a local JSON artifact for cron/CI evidence.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import shlex
import shutil
import subprocess
from typing import Any

CONTRACT_TYPE = "korea_payroll_closing_runtime_verification_v1"
RUNTIME_ACTION = "runtime_verification_read_only"
MUTATION_BOUNDARY = "read_only_no_save_submit_approve_send_provider"
AI_ROLE = "assistant_only"
WORKLIST_METHOD = (
	"hrms.regional.south_korea.payroll_closing_worklist_runtime_api."
	"list_korea_payroll_closing_worklist_runtime"
)


def build_docker_compose_ps_command(repo_root: pathlib.Path) -> list[str]:
	"""Build the Docker Compose status command for this workspace."""

	return ["docker", "compose", "-f", str(pathlib.Path(repo_root) / "docker" / "docker-compose.yml"), "ps", "--format", "json"]


def build_bench_worklist_probe_command(*, site: str, company: str, workplaces: list[str] | None = None) -> list[str]:
	"""Build a read-only bench execute command for the worklist runtime API."""

	kwargs: dict[str, Any] = {"company": _require_text(company, "company")}
	if workplaces is not None:
		if not isinstance(workplaces, list) or not all(isinstance(item, str) and item.strip() for item in workplaces):
			raise ValueError("workplaces must be a list of non-empty strings when provided")
		kwargs["workplaces"] = workplaces
	return [
		"bench",
		"--site",
		_require_text(site, "site"),
		"execute",
		WORKLIST_METHOD,
		"--kwargs",
		json.dumps(kwargs, ensure_ascii=False, sort_keys=True),
	]


def verify_runtime_checkpoint(
	*,
	repo_root: pathlib.Path,
	company: str = "Korea Demo Co",
	workplaces: list[str] | None = None,
	include_bench: bool = False,
	site: str | None = None,
	dry_run: bool = False,
) -> dict[str, Any]:
	"""Return a report-safe read-only runtime verification checkpoint."""

	repo_root = pathlib.Path(repo_root).resolve()
	docker_result = run_command(
		build_docker_compose_ps_command(repo_root),
		cwd=repo_root,
		dry_run=dry_run,
		runtime_output_parser=parse_docker_compose_runtime_available,
	)
	bench_result: dict[str, Any]
	if include_bench:
		if not site:
			raise ValueError("site is required when include_bench is true")
		if shutil.which("bench") is None and not dry_run:
			bench_result = {
				"command": "bench",
				"skipped": True,
				"reason": "bench executable not found",
				"runtime_available": False,
				"returncode": 0,
			}
		else:
			bench_result = run_command(
				build_bench_worklist_probe_command(site=site, company=company, workplaces=workplaces),
				cwd=repo_root,
				dry_run=dry_run,
				redact_output=True,
				redact_command=True,
			)
	else:
		bench_result = {
			"command": "bench execute payroll closing worklist runtime read",
			"skipped": True,
			"reason": "bench probe not requested",
			"runtime_available": False,
			"returncode": 0,
		}

	bench_check_passed = (not include_bench and bench_result.get("skipped")) or (
		bench_result.get("returncode") == 0 and not bench_result.get("skipped")
	)
	command_checks_passed = docker_result.get("returncode") == 0 and not docker_result.get("skipped") and bench_check_passed
	runtime_verified = bool(docker_result.get("runtime_available")) and (
		not include_bench or bool(bench_result.get("runtime_available"))
	)
	runtime_blockers = []
	if not runtime_verified:
		runtime_blockers.append("runtime not verified")
	if docker_result.get("returncode") != 0:
		runtime_blockers.append("docker compose status check failed")
	elif not docker_result.get("skipped") and not docker_result.get("runtime_available"):
		runtime_blockers.append("docker compose runtime not running")
	if include_bench and bench_result.get("returncode") != 0:
		runtime_blockers.append("bench worklist runtime read failed")
	return {
		"contract_type": CONTRACT_TYPE,
		"runtime_action": RUNTIME_ACTION,
		"requires_runtime_apply": False,
		"requires_human_approval": True,
		"ai_role": AI_ROLE,
		"mutation_boundary": MUTATION_BOUNDARY,
		"repo_root": str(repo_root),
		"scope": {
			"company_provided": bool(company),
			"workplace_count": len(workplaces or []),
			"site_provided": bool(site),
		},
		"docker_compose": docker_result,
		"bench_probe": bench_result,
		"command_checks_passed": command_checks_passed,
		"runtime_verified": runtime_verified,
		"runtime_blockers": runtime_blockers,
		"fixture_fallback_required_until_positive_runtime_rows": True,
		"read_only_evidence_packet_boundary": True,
		"passed": runtime_verified,
	}


def run_command(
	command: list[str],
	*,
	cwd: pathlib.Path,
	dry_run: bool = False,
	timeout_seconds: int = 30,
	redact_output: bool = True,
	redact_command: bool = False,
	runtime_output_parser: Any | None = None,
) -> dict[str, Any]:
	"""Run a command and return a redacted, report-safe result object."""

	command_text = _redact_command(command) if redact_command else shlex.join(command)
	if dry_run:
		return {"command": command_text, "skipped": True, "returncode": 0, "runtime_available": False}
	if shutil.which(command[0]) is None:
		return {
			"command": command_text,
			"skipped": True,
			"reason": f"{command[0]} executable not found",
			"returncode": 0,
			"runtime_available": False,
		}
	try:
		completed = subprocess.run(
			command,
			cwd=str(cwd),
			text=True,
			capture_output=True,
			check=False,
			timeout=timeout_seconds,
		)
	except FileNotFoundError:
		return {
			"command": command_text,
			"skipped": True,
			"reason": f"{command[0]} executable not found",
			"returncode": 0,
			"runtime_available": False,
		}
	except subprocess.TimeoutExpired:
		return {
			"command": command_text,
			"returncode": 124,
			"runtime_available": False,
			"timed_out": True,
			"timeout_seconds": timeout_seconds,
		}
	runtime_available = completed.returncode == 0 and bool(completed.stdout.strip())
	if runtime_output_parser is not None and completed.returncode == 0:
		runtime_available = runtime_output_parser(completed.stdout)
	result = {
		"command": command_text,
		"returncode": completed.returncode,
		"runtime_available": runtime_available,
		"stdout_present": bool(completed.stdout.strip()),
		"stderr_present": bool(completed.stderr.strip()),
	}
	if not redact_output:
		result["stdout_tail"] = _tail(completed.stdout)
		result["stderr_tail"] = _tail(completed.stderr)
	return result


def parse_docker_compose_runtime_available(stdout: str) -> bool:
	"""Return true only when docker compose JSON shows a running service."""

	containers = _parse_docker_compose_ps_json(stdout)
	for container in containers:
		service = str(container.get("Service") or container.get("service") or container.get("Name") or "").strip().lower()
		state = str(container.get("State") or container.get("state") or "").strip().lower()
		health = str(container.get("Health") or container.get("health") or "").strip().lower()
		if service == "frappe" and state == "running" and health not in {"unhealthy", "starting"}:
			return True
	return False


def _parse_docker_compose_ps_json(stdout: str) -> list[dict[str, Any]]:
	text = stdout.strip()
	if not text:
		return []
	try:
		parsed = json.loads(text)
	except json.JSONDecodeError:
		parsed = []
		for line in text.splitlines():
			line = line.strip()
			if not line:
				continue
			try:
				item = json.loads(line)
			except json.JSONDecodeError:
				return []
			if isinstance(item, dict):
				parsed.append(item)
		return parsed
	if isinstance(parsed, dict):
		return [parsed]
	if isinstance(parsed, list):
		return [item for item in parsed if isinstance(item, dict)]
	return []


def _redact_command(command: list[str]) -> str:
	redacted: list[str] = []
	skip_next = False
	for item in command:
		if skip_next:
			redacted.append("[redacted]")
			skip_next = False
			continue
		redacted.append(item)
		if item in {"--kwargs", "--site"}:
			skip_next = True
	return shlex.join(redacted)


def _tail(text: str, *, max_lines: int = 40) -> str:
	lines = text.splitlines()
	return "\n".join(lines[-max_lines:])


def _require_text(value: Any, fieldname: str) -> str:
	if not isinstance(value, str) or not value.strip():
		raise ValueError(f"{fieldname} must be a non-empty string")
	return value.strip()


def _coerce_workplaces(value: str | None) -> list[str] | None:
	if value is None or value.strip() == "":
		return None
	parsed = json.loads(value)
	if not isinstance(parsed, list) or not all(isinstance(item, str) and item.strip() for item in parsed):
		raise ValueError("--workplaces must be a JSON list of non-empty strings")
	return parsed


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(description="Verify Korea payroll closing runtime read path without mutation.")
	parser.add_argument("--repo-root", default=str(pathlib.Path(__file__).resolve().parents[1]))
	parser.add_argument("--company", default="Korea Demo Co")
	parser.add_argument("--workplaces", help='Optional JSON list, e.g. ["Seoul HQ"]')
	parser.add_argument("--include-bench", action="store_true")
	parser.add_argument("--site")
	parser.add_argument("--dry-run", action="store_true")
	parser.add_argument("--report-file", help="Optional path to write the JSON verification report.")
	args = parser.parse_args(argv)

	report = verify_runtime_checkpoint(
		repo_root=pathlib.Path(args.repo_root),
		company=args.company,
		workplaces=_coerce_workplaces(args.workplaces),
		include_bench=args.include_bench,
		site=args.site,
		dry_run=args.dry_run,
	)
	json_report = json.dumps(report, ensure_ascii=False, indent=2)
	print(json_report)
	if args.report_file:
		report_path = pathlib.Path(args.report_file)
		report_path.parent.mkdir(parents=True, exist_ok=True)
		report_path.write_text(json_report + "\n", encoding="utf-8")
	return 0 if report["passed"] else 1


if __name__ == "__main__":
	raise SystemExit(main())
