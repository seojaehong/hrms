"""Framework-free Korea statutory payroll reference helpers.

This module is intentionally policy-driven. It does not claim that embedded
rates are current law; callers must pass the payroll/social-insurance policy
inputs they want to apply for a payroll period.
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
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
	"industrial_accident_insurance": "Industrial Accident Insurance",
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
	industrial_accident = _employer_only_contribution(policy.get("industrial_accident_insurance"), basis)

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
	contribution_bases = {
		_STATUTORY_COMPONENTS["national_pension"]: _basis_pair(national_pension),
		_STATUTORY_COMPONENTS["health_insurance"]: _basis_pair(health_insurance),
		_STATUTORY_COMPONENTS["long_term_care_insurance"]: _basis_pair(long_term_care),
		_STATUTORY_COMPONENTS["employment_insurance"]: _basis_pair(employment_insurance),
	}
	if industrial_accident is not None:
		employer_contributions[_STATUTORY_COMPONENTS["industrial_accident_insurance"]] = industrial_accident["employer"]
		contribution_bases[_STATUTORY_COMPONENTS["industrial_accident_insurance"]] = _basis_pair(industrial_accident)

	return {
		"earnings": tax_summary["earnings"],
		"ordinary_wage": tax_summary["ordinary_wage"],
		"gross_earnings": tax_summary["gross_earnings"],
		"taxable_earnings": tax_summary["taxable_earnings"],
		"non_taxable_earnings": tax_summary["non_taxable_earnings"],
		"employee_deductions": employee_deductions,
		"employer_contributions": employer_contributions,
		"contribution_bases": contribution_bases,
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
			rate = _to_decimal(entry.get(rate_key), f"{key}.{rate_key}")
			if rate < 0:
				raise ValueError(f"{key}.{rate_key} cannot be negative")
		for limit_key in ("floor", "ceiling"):
			if entry.get(limit_key) is not None:
				limit = _to_integer_won(entry[limit_key], f"{key}.{limit_key}")
				if limit < 0:
					raise ValueError(f"{key}.{limit_key} cannot be negative")
		if (
			entry.get("floor") is not None
			and entry.get("ceiling") is not None
			and _to_integer_won(entry["floor"], f"{key}.floor") > _to_integer_won(entry["ceiling"], f"{key}.ceiling")
		):
			raise ValueError(f"{key}.floor cannot exceed {key}.ceiling")
	limit = policy.get("meal_allowance_monthly_non_taxable_limit", 0)
	limit_won = _to_integer_won(limit, "meal_allowance_monthly_non_taxable_limit")
	if limit_won < 0:
		raise ValueError("meal_allowance_monthly_non_taxable_limit cannot be negative")
	if policy.get("industrial_accident_insurance") is not None:
		_validate_industrial_accident_policy(policy["industrial_accident_insurance"])


def _validate_industrial_accident_policy(entry: dict[str, Any]) -> None:
	if not isinstance(entry, dict):
		raise ValueError("industrial_accident_insurance policy must be a dict")
	if "basis" not in entry:
		raise ValueError("industrial_accident_insurance.basis is required")
	basis = entry["basis"]
	if basis != "monthly_taxable_wage":
		raise ValueError("industrial_accident_insurance.basis must be monthly_taxable_wage")
	if "employee_rate" in entry:
		raise ValueError("industrial_accident_insurance.employee_rate is not supported")
	rate = _to_decimal(entry.get("employer_rate"), "industrial_accident_insurance.employer_rate")
	if rate < 0:
		raise ValueError("industrial_accident_insurance.employer_rate cannot be negative")
	for limit_key in ("floor", "ceiling"):
		if entry.get(limit_key) is not None:
			limit = _to_integer_won(entry[limit_key], f"industrial_accident_insurance.{limit_key}")
			if limit < 0:
				raise ValueError(f"industrial_accident_insurance.{limit_key} cannot be negative")
	if (
		entry.get("floor") is not None
		and entry.get("ceiling") is not None
		and _to_integer_won(entry["floor"], "industrial_accident_insurance.floor")
		> _to_integer_won(entry["ceiling"], "industrial_accident_insurance.ceiling")
	):
		raise ValueError("industrial_accident_insurance.floor cannot exceed industrial_accident_insurance.ceiling")


def _build_taxable_summary(lines: list[dict[str, Any]], policy: dict[str, Any], component_presets: dict[str, dict[str, Any]]) -> dict[str, Any]:
	meal_limit = _to_integer_won(policy.get("meal_allowance_monthly_non_taxable_limit", 0), "meal_allowance_monthly_non_taxable_limit")
	meal_non_taxable_remaining = meal_limit
	gross = 0
	taxable = 0
	non_taxable = 0
	ordinary_wage = 0
	enriched_lines = []

	for line in lines:
		amount = line["amount"]
		gross += amount
		preset = component_presets.get(line["component"], {})
		category = preset.get("korea_component_category")
		is_ordinary_wage = category == "Ordinary Wage" or line["component"] in _ORDINARY_WAGE_COMPONENTS
		ordinary_wage_amount = amount if is_ordinary_wage else 0
		ordinary_wage += ordinary_wage_amount
		if line["component"] == _MEAL_ALLOWANCE_COMPONENT:
			non_taxable_amount = min(amount, meal_non_taxable_remaining)
			meal_non_taxable_remaining -= non_taxable_amount
		else:
			non_taxable_amount = 0
		taxable_amount = amount - non_taxable_amount
		non_taxable += non_taxable_amount
		taxable += taxable_amount
		enriched_lines.append(
			{
				**line,
				"korea_component_category": category,
				"ordinary_wage_amount": ordinary_wage_amount,
				"taxable_amount": taxable_amount,
				"non_taxable_amount": non_taxable_amount,
			}
		)

	return {
		"earnings": enriched_lines,
		"gross_earnings": gross,
		"taxable_earnings": taxable,
		"non_taxable_earnings": non_taxable,
		"ordinary_wage": ordinary_wage,
	}


def _split_contribution(policy: dict[str, Any], employee_basis: int, *, employer_basis: int | None = None) -> dict[str, int]:
	basis = _apply_floor_ceiling(employee_basis, policy)
	employer_basis = basis if employer_basis is None else _apply_floor_ceiling(employer_basis, policy)
	return {
		"employee": _round_decimal_to_won(Decimal(basis) * _to_decimal(policy["employee_rate"], "employee_rate")),
		"employer": _round_decimal_to_won(Decimal(employer_basis) * _to_decimal(policy["employer_rate"], "employer_rate")),
		"employee_basis": basis,
		"employer_basis": employer_basis,
	}


def _employer_only_contribution(policy: dict[str, Any] | None, basis: int) -> dict[str, int] | None:
	if policy is None:
		return None
	contribution_basis = _apply_floor_ceiling(basis, policy)
	return {
		"employee": 0,
		"employer": _round_decimal_to_won(
			Decimal(contribution_basis) * _to_decimal(policy["employer_rate"], "industrial_accident_insurance.employer_rate")
		),
		"employee_basis": 0,
		"employer_basis": contribution_basis,
	}


def _basis_pair(contribution: dict[str, int]) -> dict[str, int]:
	return {"employee": contribution["employee_basis"], "employer": contribution["employer_basis"]}

def _apply_floor_ceiling(value: int, policy: dict[str, Any]) -> int:
	basis = value
	if policy.get("floor") is not None:
		basis = max(basis, _to_integer_won(policy["floor"], "floor"))
	if policy.get("ceiling") is not None:
		basis = min(basis, _to_integer_won(policy["ceiling"], "ceiling"))
	return basis


def _normalize_earning(line: dict[str, Any]) -> dict[str, Any]:
	component = str(line.get("component") or line.get("label") or "").strip()
	if not component:
		raise ValueError("earning component is required")
	amount = _to_integer_won(line.get("amount"), "earning amount")
	if amount < 0:
		raise ValueError("earning amount cannot be negative")
	return {"component": component, "amount": amount}


def _to_integer_won(value: Any, name: str) -> int:
	amount = _to_decimal(value, name)
	if amount != amount.to_integral_value():
		raise ValueError(f"{name} must be an integer KRW amount")
	return int(amount)


def _round_decimal_to_won(value: Decimal) -> int:
	return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _to_decimal(value: Any, name: str) -> Decimal:
	if isinstance(value, bool):
		raise ValueError(f"{name} must be a finite number")
	try:
		number = Decimal(str(value))
	except (InvalidOperation, ValueError) as exc:
		raise ValueError(f"{name} must be a finite number") from exc
	if not number.is_finite():
		raise ValueError(f"{name} must be a finite number")
	return number


__all__ = ["build_statutory_payroll_snapshot", "load_korea_salary_component_presets"]
