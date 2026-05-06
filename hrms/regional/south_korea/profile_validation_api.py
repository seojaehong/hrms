"""Frappe-facing preview API for Korea HR profile validation contracts.

This module is preview-only and side-effect-free. It validates Workplace Profile
and Employment Profile-shaped JSON/dict payloads before runtime save/apply steps
without importing Frappe in direct-run tests.
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
def preview_korea_hr_profile_validation(
	*,
	workplace_profile: Any | None = None,
	employment_profile: Any | None = None,
	employee_company: str | None = None,
	workplace_company: str | None = None,
) -> dict[str, Any]:
	"""Return a side-effect-free Korea HR profile validation preview."""

	validation = _load_sibling_module("profile_validation.py", "korea_profile_validation")
	workplace_result = None
	employment_result = None
	if workplace_profile is not None:
		workplace_result = validation.validate_workplace_profile(_coerce_mapping(workplace_profile, "workplace_profile"))
	if employment_profile is not None:
		employment_result = validation.validate_employment_profile(
			_coerce_mapping(employment_profile, "employment_profile"),
			employee_company=employee_company,
			workplace_company=workplace_company,
		)
	return {
		"contract_type": "korea_hr_profile_validation_preview_v1",
		"runtime_action": "preview_only",
		"requires_runtime_apply": False,
		"workplace_profile": deepcopy(workplace_result),
		"employment_profile": deepcopy(employment_result),
	}


def _coerce_mapping(value: Any, fieldname: str) -> dict[str, Any]:
	coerced = _coerce_json_if_needed(value)
	if not isinstance(coerced, dict):
		raise ValueError(f"{fieldname} must be a dict or JSON object")
	return coerced


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


__all__ = ["preview_korea_hr_profile_validation"]
