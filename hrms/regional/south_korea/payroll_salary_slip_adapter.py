"""Framework-free adapter from Salary Slip-shaped data to Korea payroll cores.

The helpers in this module intentionally avoid Frappe imports so they can be
used in direct-run tests and later wrapped by bench/Frappe whitelisted APIs.
They do not mutate Salary Slip documents; they build reviewable payloads for
statutory deductions and external verification workflow wiring.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


def build_korea_salary_slip_statutory_payload(*, salary_slip: Any, policy: dict[str, Any]) -> dict[str, Any]:
	"""Build statutory payroll rows from a Salary Slip-shaped object or dict."""

	statutory_payroll = _load_sibling_module("statutory_payroll.py", "korea_statutory_payroll")
	earnings = [_normalize_earning(row) for row in _extract_earning_rows(salary_slip)]
	snapshot = statutory_payroll.build_statutory_payroll_snapshot(earnings=earnings, policy=policy)

	return {
		"source": {"doctype": "Salary Slip", "name": _get_value(salary_slip, "name")},
		"employee": _get_value(salary_slip, "employee"),
		"company": _get_value(salary_slip, "company"),
		"period": _extract_period(salary_slip),
		"snapshot": snapshot,
		"deduction_rows": _to_salary_component_rows(
			snapshot["employee_deductions"],
			basis_by_component=snapshot.get("contribution_bases", {}),
			basis_side="employee",
		),
		"employer_contribution_rows": _to_salary_component_rows(
			snapshot["employer_contributions"],
			basis_by_component=snapshot.get("contribution_bases", {}),
			basis_side="employer",
		),
	}


def build_korea_salary_slip_verification_request(
	*,
	salary_slip: Any,
	policy: dict[str, Any],
	workplace: dict[str, Any],
	provider: dict[str, Any] | None = None,
	consent_reference: str | None = None,
) -> dict[str, Any]:
	"""Build a provider-ready verification request from Salary Slip-shaped data."""

	payroll_verification = _load_sibling_module("payroll_verification.py", "korea_payroll_verification")
	adapter_payload = build_korea_salary_slip_statutory_payload(salary_slip=salary_slip, policy=policy)
	request = payroll_verification.build_payroll_verification_request(
		snapshot=adapter_payload["snapshot"],
		period=adapter_payload["period"],
		workplace=workplace,
		provider=provider,
		consent_reference=consent_reference,
	)
	request["source"] = {
		"doctype": "Salary Slip",
		"name": adapter_payload["source"]["name"],
		"employee": adapter_payload["employee"],
		"company": adapter_payload["company"],
		"statutory_adapter_payload": adapter_payload,
	}
	return request


def _extract_earning_rows(salary_slip: Any) -> list[Any]:
	earnings = _get_value(salary_slip, "earnings", [])
	if not isinstance(earnings, list):
		raise ValueError("salary_slip.earnings must be a list")
	return earnings


def _normalize_earning(row: Any) -> dict[str, Any]:
	component = str(_get_value(row, "salary_component") or _get_value(row, "component") or _get_value(row, "label") or "").strip()
	if not component:
		raise ValueError("earning salary_component is required")
	return {"component": component, "amount": _get_value(row, "amount")}


def _extract_period(salary_slip: Any) -> dict[str, Any]:
	start_date = _require_text(_get_value(salary_slip, "start_date"), "salary_slip.start_date")
	end_date = _require_text(_get_value(salary_slip, "end_date"), "salary_slip.end_date")
	return {"start_date": start_date, "end_date": end_date}


def _to_salary_component_rows(
	amounts: dict[str, int],
	*,
	basis_by_component: dict[str, dict[str, int]] | None = None,
	basis_side: str | None = None,
) -> list[dict[str, int | str]]:
	rows = []
	for component, amount in amounts.items():
		row = {"salary_component": component, "amount": amount}
		basis = (basis_by_component or {}).get(component, {})
		if basis_side and basis_side in basis:
			row["contribution_basis"] = basis[basis_side]
		rows.append(row)
	return rows


def _get_value(source: Any, key: str, default: Any = None) -> Any:
	if isinstance(source, dict):
		return source.get(key, default)
	return getattr(source, key, default)


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


__all__ = ["build_korea_salary_slip_statutory_payload", "build_korea_salary_slip_verification_request"]
