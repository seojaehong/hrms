"""Framework-free Payroll Entry adapter for Korea payroll batch previews.

The helpers in this module intentionally avoid Frappe imports. They aggregate
Salary Slip-shaped rows into a Payroll Entry-shaped statutory payroll batch and
build a provider-ready verification request contract without saving, submitting,
or calling external providers.
"""

from __future__ import annotations

import importlib.util
from copy import deepcopy
from pathlib import Path
from typing import Any


def build_korea_payroll_entry_statutory_batch(*, payroll_entry: Any, policy: dict[str, Any]) -> dict[str, Any]:
	"""Build a side-effect-free statutory payroll batch from Payroll Entry-shaped data."""

	slip_adapter = _load_sibling_module("payroll_salary_slip_adapter.py", "korea_payroll_salary_slip_adapter")
	salary_slips = _extract_salary_slips(payroll_entry)
	company = _get_text(payroll_entry, "company")
	period = _extract_period(payroll_entry)
	payloads = []
	for salary_slip in salary_slips:
		if company:
			slip_company = _get_text(salary_slip, "company")
			if slip_company and slip_company != company:
				raise ValueError("salary_slip.company must match payroll_entry.company")
		if (
			_require_text(_get_value(salary_slip, "start_date"), "salary_slip.start_date") != period["start_date"]
			or _require_text(_get_value(salary_slip, "end_date"), "salary_slip.end_date") != period["end_date"]
		):
			raise ValueError("salary_slip period must match payroll_entry period")
		payloads.append(slip_adapter.build_korea_salary_slip_statutory_payload(salary_slip=salary_slip, policy=policy))

	return {
		"contract_type": "korea_payroll_entry_statutory_batch_v1",
		"source": {"doctype": "Payroll Entry", "name": _get_value(payroll_entry, "name")},
		"company": company or None,
		"period": period,
		"salary_slip_payloads": deepcopy(payloads),
		"totals": _aggregate_payload_totals(payloads),
		"runtime_action": "preview_only",
		"requires_runtime_apply": True,
	}


def build_korea_payroll_entry_verification_batch_request(
	*,
	payroll_entry: Any,
	policy: dict[str, Any],
	workplace: dict[str, Any],
	provider: dict[str, Any] | None = None,
	consent_reference: str | None = None,
) -> dict[str, Any]:
	"""Build a vendor-ready verification batch request for a Payroll Entry."""

	payroll_verification = _load_sibling_module("payroll_verification.py", "korea_payroll_verification")
	batch = build_korea_payroll_entry_statutory_batch(payroll_entry=payroll_entry, policy=policy)
	basis = {
		"gross_earnings": batch["totals"]["gross_earnings"],
		"taxable_earnings": batch["totals"]["taxable_earnings"],
		"non_taxable_earnings": batch["totals"]["non_taxable_earnings"],
		"employee_deductions": batch["totals"]["deductions_by_component"],
		"employer_contributions": batch["totals"]["employer_contributions_by_component"],
		"contribution_bases": deepcopy(batch["totals"]["contribution_bases"]),
		"total_employee_deductions": batch["totals"]["total_employee_deductions"],
		"total_employer_contributions": batch["totals"]["total_employer_contributions"],
		"net_reference_pay": batch["totals"]["net_reference_pay"],
		"policy_reference": batch["totals"].get("policy_reference"),
	}
	request = payroll_verification.build_payroll_verification_request(
		snapshot=basis,
		period=batch["period"],
		workplace=workplace,
		provider=provider,
		consent_reference=consent_reference,
	)
	request.update(
		{
			"request_type": "korea_payroll_entry_verification_batch_v1",
			"source": batch["source"],
			"batch_summary": {
				"salary_slip_count": len(batch["salary_slip_payloads"]),
				"total_gross_earnings": batch["totals"]["gross_earnings"],
				"total_employee_deductions": batch["totals"]["total_employee_deductions"],
				"total_employer_contributions": batch["totals"]["total_employer_contributions"],
			},
			"statutory_batch_payload": deepcopy(batch),
			"runtime_action": "preview_only",
			"requires_runtime_apply": True,
			"requires_human_approval": True,
		}
	)
	return request


def _extract_salary_slips(payroll_entry: Any) -> list[Any]:
	salary_slips = _get_value(payroll_entry, "salary_slips", [])
	if not isinstance(salary_slips, list):
		raise ValueError("payroll_entry.salary_slips must be a list")
	if not salary_slips:
		raise ValueError("payroll_entry.salary_slips must not be empty")
	return salary_slips


def _extract_period(payroll_entry: Any) -> dict[str, str | None]:
	return {
		"start_date": _require_text(_get_value(payroll_entry, "start_date"), "payroll_entry.start_date"),
		"end_date": _require_text(_get_value(payroll_entry, "end_date"), "payroll_entry.end_date"),
		"posting_date": _get_text(payroll_entry, "posting_date") or None,
	}


def _aggregate_payload_totals(payloads: list[dict[str, Any]]) -> dict[str, Any]:
	deductions: dict[str, int] = {}
	employer_contributions: dict[str, int] = {}
	contribution_bases: dict[str, dict[str, int]] = {}
	totals = {
		"gross_earnings": 0,
		"taxable_earnings": 0,
		"non_taxable_earnings": 0,
		"ordinary_wage": 0,
		"total_employee_deductions": 0,
		"total_employer_contributions": 0,
		"net_reference_pay": 0,
		"policy_reference": None,
	}
	for payload in payloads:
		snapshot = payload["snapshot"]
		for key in (
			"gross_earnings",
			"taxable_earnings",
			"non_taxable_earnings",
			"ordinary_wage",
			"total_employee_deductions",
			"total_employer_contributions",
			"net_reference_pay",
		):
			totals[key] += int(snapshot[key])
		if totals["policy_reference"] is None:
			totals["policy_reference"] = snapshot.get("policy_reference")
		elif totals["policy_reference"] != snapshot.get("policy_reference"):
			raise ValueError("salary slip policy references must match within a payroll entry batch")
		_add_component_amounts(deductions, snapshot["employee_deductions"])
		_add_component_amounts(employer_contributions, snapshot["employer_contributions"])
		_add_component_bases(contribution_bases, snapshot.get("contribution_bases", {}))
	totals["deductions_by_component"] = deductions
	totals["employer_contributions_by_component"] = employer_contributions
	totals["contribution_bases"] = contribution_bases
	return totals


def _add_component_amounts(target: dict[str, int], amounts: dict[str, int]) -> None:
	for component, amount in amounts.items():
		target[component] = target.get(component, 0) + int(amount)


def _add_component_bases(target: dict[str, dict[str, int]], bases: dict[str, dict[str, int]]) -> None:
	for component, sides in bases.items():
		if component not in target:
			target[component] = {"employee": 0, "employer": 0}
		for side in ("employee", "employer"):
			target[component][side] += int(sides.get(side, 0))


def _get_value(source: Any, key: str, default: Any = None) -> Any:
	if isinstance(source, dict):
		return source.get(key, default)
	return getattr(source, key, default)


def _get_text(source: Any, key: str) -> str:
	return str(_get_value(source, key) or "").strip()


def _require_text(value: Any, name: str) -> str:
	text = str(value or "").strip()
	if not text:
		raise ValueError(f"{name} is required")
	return text


def _load_sibling_module(filename: str, module_name: str):
	path = Path(__file__).with_name(filename)
	spec = importlib.util.spec_from_file_location(module_name, path)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


__all__ = [
	"build_korea_payroll_entry_statutory_batch",
	"build_korea_payroll_entry_verification_batch_request",
]
