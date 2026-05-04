"""Framework-free Korea statutory payroll reference helpers.

This module is intentionally policy-driven. It does not claim that embedded
rates are current law; callers must pass the payroll/social-insurance policy
inputs they want to apply for a payroll period.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

_REQUIRED_POLICIES = (
	"national_pension",
	"health_insurance",
	"long_term_care_insurance",
	"employment_insurance",
)

_STATUTORY_COMPONENTS = {
	"national_pension": "National Pension",
	"health_insurance": "Health Insurance",
	"long_term_care_insurance": "Long-term Care Insurance",
	"employment_insurance": "Employment Insurance",
}

_ORDINARY_WAGE_COMPONENTS = {"Basic Pay"}
_MEAL_ALLOWANCE_COMPONENT = "Meal Allowance"


def build_statutory_payroll_snapshot(*, earnings: list[dict[str, Any]], policy: dict[str, Any]) -> dict[str, Any]:
	"""Build a deterministic Korea statutory payroll reference snapshot.

	The return value is suitable for Salary Slip adapter work later, but remains
	framework-free for direct unit tests and policy review. Monetary values are
	integer KRW rounded to the nearest won.
	"""

	_validate_policy(policy)
	component_presets = load_korea_salary_component_presets()
	lines = [_normalize_earning(line) for line in earnings]
	tax_summary = _build_taxable_summary(lines, policy, component_presets)
	basis = tax_summary["taxable_earnings"]

	national_pension = _split_contribution(policy["national_pension"], basis)
	health_insurance = _split_contribution(policy["health_insurance"], basis)
	long_term_care = _split_contribution(
		policy["long_term_care_insurance"],
		health_insurance["employee"],
		employer_basis=health_insurance["employer"],
	)
	employment_insurance = _split_contribution(policy["employment_insurance"], basis)

	employee_deductions = {
		_STATUTORY_COMPONENTS["national_pension"]: national_pension["employee"],
		_STATUTORY_COMPONENTS["health_insurance"]: health_insurance["employee"],
		_STATUTORY_COMPONENTS["long_term_care_insurance"]: long_term_care["employee"],
		_STATUTORY_COMPONENTS["employment_insurance"]: employment_insurance["employee"],
	}
	employer_contributions = {
		_STATUTORY_COMPONENTS["national_pension"]: national_pension["employer"],
		_STATUTORY_COMPONENTS["health_insurance"]: health_insurance["employer"],
		_STATUTORY_COMPONENTS["long_term_care_insurance"]: long_term_care["employer"],
		_STATUTORY_COMPONENTS["employment_insurance"]: employment_insurance["employer"],
	}

	return {
		"earnings": lines,
		"ordinary_wage": tax_summary["ordinary_wage"],
		"gross_earnings": tax_summary["gross_earnings"],
		"taxable_earnings": tax_summary["taxable_earnings"],
		"non_taxable_earnings": tax_summary["non_taxable_earnings"],
		"employee_deductions": employee_deductions,
		"employer_contributions": employer_contributions,
		"total_employee_deductions": sum(employee_deductions.values()),
		"total_employer_contributions": sum(employer_contributions.values()),
		"net_reference_pay": tax_summary["gross_earnings"] - sum(employee_deductions.values()),
		"policy_reference": policy.get("reference"),
	}


def load_korea_salary_component_presets() -> dict[str, dict[str, Any]]:
	"""Load South Korea salary component presets keyed by component name."""

	path = Path(__file__).with_name("data") / "salary_components.json"
	with path.open(encoding="utf-8") as handle:
		components = json.load(handle)
	return {item["salary_component"]: item for item in components}


def _validate_policy(policy: dict[str, Any]) -> None:
	if not isinstance(policy, dict):
		raise ValueError("policy must be a dict")
	for key in _REQUIRED_POLICIES:
		if key not in policy:
			raise ValueError(f"{key} policy is required")
		entry = policy[key]
		if not isinstance(entry, dict):
			raise ValueError(f"{key} policy must be a dict")
		expected_basis = "health_insurance" if key == "long_term_care_insurance" else "monthly_taxable_wage"
		basis = entry.get("basis", expected_basis)
		if basis != expected_basis:
			raise ValueError(f"{key}.basis must be {expected_basis}")
		for rate_key in ("employee_rate", "employer_rate"):
			_validate_number(entry.get(rate_key), f"{key}.{rate_key}")
			if float(entry[rate_key]) < 0:
				raise ValueError(f"{key}.{rate_key} cannot be negative")
		for limit_key in ("floor", "ceiling"):
			if entry.get(limit_key) is not None:
				_validate_number(entry[limit_key], f"{key}.{limit_key}")
				if float(entry[limit_key]) < 0:
					raise ValueError(f"{key}.{limit_key} cannot be negative")
		if entry.get("floor") is not None and entry.get("ceiling") is not None and float(entry["floor"]) > float(entry["ceiling"]):
			raise ValueError(f"{key}.floor cannot exceed {key}.ceiling")
	limit = policy.get("meal_allowance_monthly_non_taxable_limit", 0)
	_validate_number(limit, "meal_allowance_monthly_non_taxable_limit")
	if float(limit) < 0:
		raise ValueError("meal_allowance_monthly_non_taxable_limit cannot be negative")


def _build_taxable_summary(lines: list[dict[str, Any]], policy: dict[str, Any], component_presets: dict[str, dict[str, Any]]) -> dict[str, int]:
	meal_limit = _to_won(policy.get("meal_allowance_monthly_non_taxable_limit", 0))
	meal_non_taxable_remaining = meal_limit
	gross = 0
	taxable = 0
	non_taxable = 0
	ordinary_wage = 0

	for line in lines:
		amount = line["amount"]
		gross += amount
		preset = component_presets.get(line["component"], {})
		if preset.get("korea_component_category") == "Ordinary Wage" or line["component"] in _ORDINARY_WAGE_COMPONENTS:
			ordinary_wage += amount
		if line["component"] == _MEAL_ALLOWANCE_COMPONENT:
			non_taxable_amount = min(amount, meal_non_taxable_remaining)
			meal_non_taxable_remaining -= non_taxable_amount
		else:
			non_taxable_amount = 0
		non_taxable += non_taxable_amount
		taxable += amount - non_taxable_amount

	return {
		"gross_earnings": gross,
		"taxable_earnings": taxable,
		"non_taxable_earnings": non_taxable,
		"ordinary_wage": ordinary_wage,
	}


def _split_contribution(policy: dict[str, Any], employee_basis: int, *, employer_basis: int | None = None) -> dict[str, int]:
	basis = _apply_floor_ceiling(employee_basis, policy)
	employer_basis = basis if employer_basis is None else _apply_floor_ceiling(employer_basis, policy)
	return {
		"employee": _to_won(basis * float(policy["employee_rate"])),
		"employer": _to_won(employer_basis * float(policy["employer_rate"])),
	}


def _apply_floor_ceiling(value: int, policy: dict[str, Any]) -> int:
	basis = value
	if policy.get("floor") is not None:
		_validate_number(policy["floor"], "floor")
		basis = max(basis, _to_won(policy["floor"]))
	if policy.get("ceiling") is not None:
		_validate_number(policy["ceiling"], "ceiling")
		basis = min(basis, _to_won(policy["ceiling"]))
	return basis


def _normalize_earning(line: dict[str, Any]) -> dict[str, Any]:
	component = str(line.get("component") or line.get("label") or "").strip()
	if not component:
		raise ValueError("earning component is required")
	amount = _to_won(line.get("amount"))
	if amount < 0:
		raise ValueError("earning amount cannot be negative")
	return {"component": component, "amount": amount}


def _to_won(value: Any) -> int:
	_validate_number(value, "amount")
	return int(round(float(value)))


def _validate_number(value: Any, name: str) -> None:
	if isinstance(value, bool):
		raise ValueError(f"{name} must be a finite number")
	try:
		number = float(value)
	except (TypeError, ValueError) as exc:
		raise ValueError(f"{name} must be a finite number") from exc
	if not math.isfinite(number):
		raise ValueError(f"{name} must be a finite number")


__all__ = ["build_statutory_payroll_snapshot", "load_korea_salary_component_presets"]
