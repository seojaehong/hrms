"""Frappe-facing preview API for Korea Salary Slip payroll contracts.

This module is intentionally preview-only: it reads Salary Slip-shaped data,
returns framework-free statutory payroll / verification contracts, and never
saves, submits, or mutates Frappe documents. Direct file tests can run without a
bench; when Frappe is present the functions are whitelisted.
"""

from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

try:  # pragma: no cover - exercised only inside a Frappe bench
	import frappe  # type: ignore
except ImportError:  # pragma: no cover - direct-run no-bench mode
	frappe = None  # type: ignore


def _whitelist(fn):
	if frappe is None:
		return fn
	return frappe.whitelist()(fn)


@_whitelist
def preview_korea_salary_slip_statutory_payload(*, salary_slip: Any, policy: Any) -> dict[str, Any]:
	"""Return a side-effect-free statutory payroll preview for a Salary Slip."""

	adapter = _load_sibling_module("payroll_salary_slip_adapter.py", "korea_payroll_salary_slip_adapter")
	salary_slip_doc = _resolve_salary_slip(salary_slip)
	payload = adapter.build_korea_salary_slip_statutory_payload(
		salary_slip=salary_slip_doc,
		policy=_coerce_mapping(policy, "policy"),
	)
	payload = deepcopy(payload)
	payload.update(
		{
			"contract_type": "korea_salary_slip_statutory_preview_v1",
			"runtime_action": "preview_only",
			"requires_runtime_apply": True,
		}
	)
	return payload


@_whitelist
def preview_korea_salary_slip_verification_request(
	*,
	salary_slip: Any,
	policy: Any,
	workplace: Any,
	provider: Any | None = None,
	consent_reference: str | None = None,
) -> dict[str, Any]:
	"""Return a vendor-ready verification request preview for a Salary Slip."""

	adapter = _load_sibling_module("payroll_salary_slip_adapter.py", "korea_payroll_salary_slip_adapter")
	salary_slip_doc = _resolve_salary_slip(salary_slip)
	request = adapter.build_korea_salary_slip_verification_request(
		salary_slip=salary_slip_doc,
		policy=_coerce_mapping(policy, "policy"),
		workplace=_coerce_mapping(workplace, "workplace"),
		provider=_coerce_optional_mapping(provider, "provider"),
		consent_reference=consent_reference,
	)
	request = deepcopy(request)
	request.update(
		{
			"contract_type": "korea_salary_slip_verification_preview_v1",
			"runtime_action": "preview_only",
			"requires_runtime_apply": True,
		}
	)
	request.setdefault("source", {})["doctype"] = "Salary Slip"
	return request


def _resolve_salary_slip(value: Any) -> Any:
	coerced = _coerce_json_if_needed(value)
	if isinstance(coerced, dict):
		return coerced
	if isinstance(coerced, str) and coerced.strip():
		if frappe is None:
			raise RuntimeError("Frappe runtime is required to load Salary Slip by name")
		return frappe.get_doc("Salary Slip", coerced.strip())  # type: ignore[union-attr]
	raise ValueError("salary_slip must be a dict payload or Salary Slip name")


def _coerce_mapping(value: Any, fieldname: str) -> dict[str, Any]:
	coerced = _coerce_json_if_needed(value)
	if not isinstance(coerced, dict):
		raise ValueError(f"{fieldname} must be a dict or JSON object")
	return coerced


def _coerce_optional_mapping(value: Any, fieldname: str) -> dict[str, Any] | None:
	if value in (None, ""):
		return None
	return _coerce_mapping(value, fieldname)


def _coerce_json_if_needed(value: Any) -> Any:
	if isinstance(value, str):
		text = value.strip()
		if text.startswith("{") or text.startswith("["):
			try:
				return json.loads(text)
			except json.JSONDecodeError as exc:
				raise ValueError("JSON payload is invalid") from exc
	return value


def _load_sibling_module(filename: str, module_name: str):
	path = Path(__file__).with_name(filename)
	spec = importlib.util.spec_from_file_location(module_name, path)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


__all__ = [
	"preview_korea_salary_slip_statutory_payload",
	"preview_korea_salary_slip_verification_request",
]
