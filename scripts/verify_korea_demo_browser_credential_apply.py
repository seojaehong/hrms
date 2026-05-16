#!/usr/bin/env python3
"""Cron-safe Gate 14 credential apply + browser runtime checkpoint.

This checkpoint is intentionally narrow. It can apply only the approved demo
browser user's credential when both an operator-provided secret environment value
and an explicit human approval flag are present, then runs the authenticated
browser verifier. It never prints or stores the password and it does not submit,
approve, send, call providers, or create payroll documents.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shlex
import subprocess
from typing import Any, Callable, Mapping, NamedTuple

CONTRACT_TYPE = "korea_demo_browser_credential_apply_checkpoint_v1"
RUNTIME_ACTION = "credential_apply_and_browser_verification_checkpoint"
MUTATION_BOUNDARY = "credential_only_then_browser_read_only_no_payroll_submit_approve_send_provider_call"
AI_ROLE = "assistant_only"
DEFAULT_SITE = "hrms.localhost"
DEFAULT_COMPANY = "노란봉투법 데모"
DEFAULT_BASE_URL = "http://hrms.localhost:8000"
DEFAULT_USERNAME = "demo.hr.manager@node.pe.kr"
PASSWORD_ENV_VAR = "FRAPPE_BROWSER_PASSWORD"


class CommandResult(NamedTuple):
	returncode: int
	stdout: str = ""
	stderr: str = ""


def main() -> int:
	args = parse_args()
	report = verify_demo_browser_credential_apply(
		repo_root=pathlib.Path(args.repo_root),
		site=args.site,
		company=args.company,
		base_url=args.base_url,
		username=args.username,
		chromium=args.chromium,
		human_approved=args.human_approved,
		dry_run=args.dry_run,
	)
	json_report = json.dumps(report, ensure_ascii=False, indent=2)
	print(json_report)
	if args.report_file:
		report_path = pathlib.Path(args.report_file)
		report_path.parent.mkdir(parents=True, exist_ok=True)
		report_path.write_text(json_report + "\n", encoding="utf-8")
	return 0 if report.get("runtime_verified") else 1


def verify_demo_browser_credential_apply(
	*,
	repo_root: pathlib.Path,
	environ: Mapping[str, str] | None = None,
	site: str = DEFAULT_SITE,
	company: str = DEFAULT_COMPANY,
	base_url: str = DEFAULT_BASE_URL,
	username: str = DEFAULT_USERNAME,
	chromium: str = "chromium-browser",
	human_approved: bool = False,
	dry_run: bool = False,
	run_command: Callable[..., CommandResult] | None = None,
) -> dict[str, Any]:
	repo_root = pathlib.Path(repo_root).resolve()
	environ = dict(os.environ if environ is None else environ)
	run_command = run_command or _run_subprocess
	password = environ.get(PASSWORD_ENV_VAR)
	report: dict[str, Any] = base_report(repo_root=repo_root, site=site, company=company, base_url=base_url, username=username)

	scope_error = required_scope_input_error(
		site=site,
		company=company,
		base_url=base_url,
		username=username,
		chromium=chromium,
	)
	if scope_error:
		report["credential_apply"] = skipped_step(scope_error)
		report["browser_verification"] = skipped_step("credential apply not ready")
		return report

	if not password:
		report["credential_apply"] = skipped_step("FRAPPE_BROWSER_PASSWORD missing")
		report["browser_verification"] = skipped_step("credential apply not ready")
		return report
	if not password.strip():
		report["credential_apply"] = skipped_step("FRAPPE_BROWSER_PASSWORD blank")
		report["browser_verification"] = skipped_step("credential apply not ready")
		return report
	if human_approved is not True:
		report["credential_apply"] = skipped_step("human approval flag missing")
		report["browser_verification"] = skipped_step("credential apply not approved")
		return report

	apply_command = build_docker_credential_apply_command(repo_root=repo_root, site=site)
	apply_env = {**os.environ, **environ, PASSWORD_ENV_VAR: password}
	if dry_run:
		apply_result = CommandResult(returncode=0, stdout=json.dumps({"dry_run": True, "credential_ready_for_browser_verifier": True}), stderr="")
	else:
		apply_result = run_command(apply_command, cwd=repo_root, env=apply_env, timeout=240)
	report["credential_apply"] = summarize_apply_result(apply_result, command=redact_command(apply_command), dry_run=dry_run)
	if not report["credential_apply"]["passed"]:
		report["browser_verification"] = skipped_step("credential apply failed")
		return report

	browser_command = build_browser_verifier_command(
		base_url=base_url,
		company=company,
		username=username,
		chromium=chromium,
	)
	if dry_run:
		browser_result = CommandResult(returncode=0, stdout=json.dumps({"dry_run": True, "runtime_verified": False, "fixture_fallback_required": True}), stderr="")
	else:
		browser_result = run_command(browser_command, cwd=repo_root, env=apply_env, timeout=300)
	browser_summary = summarize_browser_result(browser_result, command=redact_command(browser_command), dry_run=dry_run)
	report["browser_verification"] = browser_summary
	report["runtime_verified"] = bool(browser_summary.get("runtime_verified"))
	report["fixture_fallback_required"] = not report["runtime_verified"]
	return report


def base_report(*, repo_root: pathlib.Path, site: str, company: str, base_url: str, username: str) -> dict[str, Any]:
	return {
		"contract_type": CONTRACT_TYPE,
		"runtime_action": RUNTIME_ACTION,
		"requires_runtime_apply": False,
		"requires_human_approval": True,
		"ai_role": AI_ROLE,
		"mutation_boundary": MUTATION_BOUNDARY,
		"repo_root": str(repo_root),
		"scope": {
			"site_provided": bool(site),
			"company_provided": bool(company),
			"base_url_provided": bool(base_url),
			"username": username,
			"password_env_var": PASSWORD_ENV_VAR,
		},
		"credential_apply": skipped_step("not started"),
		"browser_verification": skipped_step("not started"),
		"runtime_verified": False,
		"fixture_fallback_required": True,
	}


def skipped_step(reason: str) -> dict[str, Any]:
	return {"attempted": False, "passed": False, "reason": reason}


def build_docker_credential_apply_command(*, repo_root: pathlib.Path, site: str) -> list[str]:
	bench_command = shlex.join([
		"bench",
		"--site",
		_require_text(site, "site"),
		"execute",
		"hrms.regional.south_korea.demo_seed.ensure_demo_browser_credential",
		"--kwargs",
		json.dumps({"human_approved": True}, sort_keys=True),
	])
	return [
		"docker",
		"compose",
		"-f",
		str(pathlib.Path(repo_root) / "docker" / "docker-compose.yml"),
		"exec",
		"-T",
		"-e",
		PASSWORD_ENV_VAR,
		"frappe",
		"bash",
		"-lc",
		f"cd /home/frappe/frappe-bench && {bench_command}",
	]


def build_browser_verifier_command(*, base_url: str, company: str, username: str, chromium: str) -> list[str]:
	return [
		"node",
		"scripts/verify_korea_payroll_closing_browser_runtime.mjs",
		"--base-url",
		_require_text(base_url, "base_url"),
		"--company",
		_require_text(company, "company"),
		"--username",
		_require_text(username, "username"),
		"--chromium",
		_require_text(chromium, "chromium"),
	]


def summarize_apply_result(result: CommandResult, *, command: list[str], dry_run: bool) -> dict[str, Any]:
	payload = parse_json_payload(result.stdout)
	apply_metadata_valid = (
		payload.get("contract_type") == "korea_demo_browser_credential_runtime_apply_v1"
		and payload.get("runtime_action") == "demo_credential_runtime_apply"
		and payload.get("requires_runtime_apply") is False
		and payload.get("requires_human_approval") is True
		and payload.get("ai_role") == AI_ROLE
		and payload.get("mutation_boundary") == "credential_only_no_payroll_submit_approve_send_provider_call"
		and payload.get("human_approval_verified") is True
	)
	credential_ready = payload.get("credential_ready_for_browser_verifier") is True or payload.get("dry_run") is True
	passed = result.returncode == 0 and (dry_run or (credential_ready and apply_metadata_valid))
	summary = {
		"attempted": True,
		"passed": passed,
		"returncode": result.returncode,
		"stdout_present": bool(result.stdout),
		"stderr_present": bool(result.stderr),
		"command": command,
		"dry_run": dry_run,
		"password_value": "[redacted]",
		"contract_type": payload.get("contract_type"),
		"runtime_action": payload.get("runtime_action"),
		"credential_ready_for_browser_verifier": payload.get("credential_ready_for_browser_verifier") is True,
		"human_approval_verified": payload.get("human_approval_verified") is True,
	}
	if result.returncode == 0 and credential_ready and not (dry_run or apply_metadata_valid):
		summary["reason"] = "credential apply safety metadata invalid"
	elif result.returncode != 0:
		summary["reason"] = "credential apply command failed"
	elif not credential_ready:
		summary["reason"] = "credential apply payload not ready"
	return summary


def summarize_browser_result(result: CommandResult, *, command: list[str], dry_run: bool) -> dict[str, Any]:
	payload = parse_json_payload(result.stdout)
	safety_metadata_valid = (
		payload.get("contract_type") == "korea_payroll_closing_browser_runtime_walkthrough_v1"
		and payload.get("runtime_action") == "browser_runtime_read_only"
		and payload.get("requires_runtime_apply") is False
		and payload.get("requires_human_approval") is True
		and payload.get("ai_role") == AI_ROLE
		and payload.get("mutation_boundary") == "read_only_no_save_submit_approve_send_provider"
	)
	payload_runtime_verified = payload.get("runtime_verified") is True and payload.get("fixture_fallback_required") is False
	passed = result.returncode == 0 and payload_runtime_verified and safety_metadata_valid
	summary = {
		"attempted": True,
		"passed": passed,
		"returncode": result.returncode,
		"stdout_present": bool(result.stdout),
		"stderr_present": bool(result.stderr),
		"command": command,
		"dry_run": dry_run,
		"contract_type": payload.get("contract_type"),
		"runtime_action": payload.get("runtime_action"),
		"runtime_verified": passed,
		"fixture_fallback_required": not passed,
	}
	if result.returncode == 0 and payload_runtime_verified and not safety_metadata_valid:
		summary["reason"] = "browser verifier safety metadata invalid"
	elif result.returncode != 0:
		summary["reason"] = "browser verifier command failed"
	elif not payload_runtime_verified:
		summary["reason"] = "browser verifier did not confirm runtime proof"
	return summary


def parse_json_payload(text: str) -> dict[str, Any]:
	text = (text or "").strip()
	if not text:
		return {}
	payload = _json_object_or_empty(text)
	if payload:
		return payload
	lines = [line for line in text.splitlines() if line.strip()]
	for index in range(len(lines) - 1, -1, -1):
		payload = _json_object_or_empty("\n".join(lines[index:]))
		if payload:
			return payload
	return _last_json_object_or_empty(text)


def _json_object_or_empty(text: str) -> dict[str, Any]:
	try:
		payload = json.loads(text)
	except json.JSONDecodeError:
		return {}
	return payload if isinstance(payload, dict) else {}


def _last_json_object_or_empty(text: str) -> dict[str, Any]:
	decoder = json.JSONDecoder()
	payload: dict[str, Any] = {}
	payload_end = -1
	for index, char in enumerate(text):
		if char != "{":
			continue
		try:
			candidate, end = decoder.raw_decode(text[index:])
		except json.JSONDecodeError:
			continue
		absolute_end = index + end
		if isinstance(candidate, dict) and absolute_end > payload_end:
			payload = candidate
			payload_end = absolute_end
	return payload


def redact_command(command: list[str]) -> list[str]:
	redacted = []
	for item in command:
		if PASSWORD_ENV_VAR in item:
			redacted.append(item.replace(PASSWORD_ENV_VAR, "FRAPPE_BROWSER_PASSWORD").replace(os.environ.get(PASSWORD_ENV_VAR, ""), "[redacted]") if os.environ.get(PASSWORD_ENV_VAR) else item)
		elif "password" in item.lower():
			redacted.append("[redacted]")
		else:
			redacted.append(item)
	return redacted


def _run_subprocess(command: list[str], **kwargs) -> CommandResult:
	completed = subprocess.run(command, text=True, capture_output=True, **kwargs)
	return CommandResult(returncode=completed.returncode, stdout=completed.stdout, stderr=completed.stderr)


def required_scope_input_error(*, site: str, company: str, base_url: str, username: str, chromium: str) -> str | None:
	for label, value in (
		("site", site),
		("company", company),
		("base_url", base_url),
		("username", username),
		("chromium", chromium),
	):
		if not isinstance(value, str) or not value.strip():
			return f"{label} must be a non-empty string"
	return None


def _require_text(value: str, label: str) -> str:
	if not isinstance(value, str) or not value.strip():
		raise ValueError(f"{label} must be a non-empty string")
	return value.strip()


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--repo-root", default=str(pathlib.Path(__file__).resolve().parents[1]))
	parser.add_argument("--site", default=DEFAULT_SITE)
	parser.add_argument("--company", default=DEFAULT_COMPANY)
	parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
	parser.add_argument("--username", default=DEFAULT_USERNAME)
	parser.add_argument("--chromium", default=os.environ.get("CHROMIUM_BIN", "chromium-browser"))
	parser.add_argument("--human-approved", action="store_true")
	parser.add_argument("--dry-run", action="store_true")
	parser.add_argument("--report-file")
	return parser.parse_args()


if __name__ == "__main__":
	raise SystemExit(main())
