"""Framework-free adapter from Salary Slip-shaped data to Korea payroll cores.

The helpers in this module intentionally avoid Frappe imports so they can be
used in direct-run tests and later wrapped by bench/Frappe whitelisted APIs.
They do not mutate Salary Slip documents; they build reviewable payloads for
statutory deductions and external verification workflow wiring.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
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


def apply_korea_statutory_to_salary_slip(*, salary_slip: Any, statutory_payload: dict[str, Any], actor: str) -> dict[str, Any]:
	"""Apply statutory deduction rows to a draft Salary Slip-shaped document.

	This is the first narrow runtime boundary for Salary Slip rows. It mutates only
	the caller-provided in-memory document/table rows; it does not save, submit,
	approve, send notifications, call providers, or commit a database transaction.
	"""

	actor_text = _require_text(actor, "actor")
	if not isinstance(statutory_payload, dict):
		raise ValueError("statutory_payload must be a dict")
	docstatus = _get_value(salary_slip, "docstatus", 0)
	if docstatus == 1:
		raise ValueError("submitted Salary Slips cannot be mutated")
	if docstatus not in (0, None):
		raise ValueError("draft Salary Slips only")

	source = statutory_payload.get("source")
	if not isinstance(source, dict) or source.get("doctype") != "Salary Slip":
		raise ValueError("statutory_payload.source must reference a Salary Slip")
	slip_name = _get_value(salary_slip, "name")
	payload_name = source.get("name")
	if slip_name and payload_name and slip_name != payload_name:
		raise ValueError("salary_slip.name does not match statutory payload source")

	deduction_rows = statutory_payload.get("deduction_rows")
	if not isinstance(deduction_rows, list):
		raise ValueError("statutory_payload.deduction_rows must be a list")
	employer_rows = statutory_payload.get("employer_contribution_rows", [])
	if not isinstance(employer_rows, list):
		raise ValueError("statutory_payload.employer_contribution_rows must be a list")
	employer_row_dicts = [_row_to_dict(row) for row in employer_rows]
	component_names = {_require_text(_get_value(row, "salary_component"), "deduction_rows.salary_component") for row in deduction_rows}

	existing_deductions = _extract_mutable_child_rows(salary_slip, "deductions")
	preserved_rows = [row for row in existing_deductions if _get_value(row, "salary_component") not in component_names]
	new_rows = [_build_child_row_like(existing_deductions, row) for row in deduction_rows]
	_replace_child_rows(salary_slip, "deductions", preserved_rows + new_rows)

	return {
		"contract_type": "korea_salary_slip_statutory_apply_result_v1",
		"runtime_action": "runtime_salary_slip_rows_applied",
		"requires_runtime_apply": False,
		"requires_human_approval": True,
		"ai_role": "assistant_only",
		"mutation_boundary": "salary_slip_rows_only_no_submit_no_approve_no_send_no_provider_call",
		"actor": actor_text,
		"salary_slip": {"doctype": "Salary Slip", "name": slip_name or payload_name},
		"applied_deduction_count": len(new_rows),
		"preserved_deduction_count": len(preserved_rows),
		"employer_contribution_rows": employer_row_dicts,
	}


def apply_korea_salary_slip_statutory_hook(salary_slip: Any, method: str | None = None) -> dict[str, Any]:
	"""Opt-in Salary Slip hook for Korea statutory rows.

	The hook is deliberately a no-op unless an operator sets the strict boolean
	``apply_korea_statutory_payroll`` flag and provides a policy plus human actor.
	"""

	apply_flag = _get_value(salary_slip, "apply_korea_statutory_payroll", False)
	if apply_flag in (False, None, 0):
		return {
			"contract_type": "korea_salary_slip_statutory_apply_hook_v1",
			"runtime_action": "skipped",
			"reason": "apply_korea_statutory_payroll not enabled",
			"requires_human_approval": True,
			"ai_role": "assistant_only",
		}
	if apply_flag not in (True, 1):
		raise ValueError("apply_korea_statutory_payroll must be a bool-like check value")

	region = _require_text(_get_value(salary_slip, "korea_statutory_region"), "korea_statutory_region")
	if region != "KR":
		raise ValueError("korea_statutory_region must be KR")
	payload = _get_value(salary_slip, "korea_statutory_payload")
	if not isinstance(payload, dict):
		raise ValueError("korea_statutory_payload must be an existing statutory preview payload")
	actor = _get_value(salary_slip, "korea_statutory_apply_actor")
	result = apply_korea_statutory_to_salary_slip(salary_slip=salary_slip, statutory_payload=payload, actor=actor)
	result["hook_method"] = method
	return result


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


def _extract_mutable_child_rows(source: Any, key: str) -> list[Any]:
	rows = _get_value(source, key, [])
	if rows is None:
		rows = []
	if not isinstance(rows, list):
		raise ValueError(f"salary_slip.{key} must be a list")
	return rows


def _replace_child_rows(source: Any, key: str, rows: list[Any]) -> None:
	if isinstance(source, dict):
		source[key] = [_row_to_dict(row) for row in rows]
		return
	if callable(getattr(source, "set", None)) and callable(getattr(source, "append", None)):
		source.set(key, [])
		for row in rows:
			source.append(key, _row_to_dict(row))
		return
	setattr(source, key, rows)


def _build_child_row_like(existing_rows: list[Any], row: Any) -> Any:
	data = _row_to_dict(row)
	if existing_rows and all(isinstance(existing, dict) for existing in existing_rows):
		return data
	return SimpleNamespace(**data)


def _row_to_dict(row: Any) -> dict[str, Any]:
	if isinstance(row, dict):
		return dict(row)
	if callable(getattr(row, "as_dict", None)):
		return dict(row.as_dict())
	if hasattr(row, "__dict__"):
		return {key: value for key, value in vars(row).items() if not key.startswith("_")}
	return {
		"salary_component": _get_value(row, "salary_component"),
		"amount": _get_value(row, "amount"),
		**(
			{"contribution_basis": _get_value(row, "contribution_basis")}
			if _get_value(row, "contribution_basis") is not None
			else {}
		),
	}


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


__all__ = [
	"build_korea_salary_slip_statutory_payload",
	"build_korea_salary_slip_verification_request",
	"apply_korea_statutory_to_salary_slip",
	"apply_korea_salary_slip_statutory_hook",
]
