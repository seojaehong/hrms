"""Frappe-facing preview API for Korea employment contract snapshots.

This module is preview-only. It normalizes JSON/dict employment profile inputs
and delegates to the framework-free employment contract helper without saving a
DocType, creating a contract record, or applying any runtime side effect.
"""

from __future__ import annotations

import datetime as dt
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
def preview_korea_employment_contract_snapshot(*, employment_profile: Any) -> dict[str, Any]:
	"""Return a side-effect-free Korea employment contract snapshot preview."""

	profile = _coerce_mapping(employment_profile, "employment_profile")
	employment_contract = _load_sibling_module("employment_contract.py", "korea_employment_contract")
	contract_snapshot = employment_contract.build_contract_snapshot(
		employee=profile.get("employee"),
		company=profile.get("company"),
		workplace=profile.get("workplace"),
		start_date=_coerce_date(profile.get("start_date"), "start_date"),
		end_date=_coerce_optional_date(profile.get("end_date"), "end_date"),
		job_title=profile.get("job_title"),
		employment_type=profile.get("employment_type"),
		working_hours_per_week=_coerce_float(profile.get("working_hours_per_week"), "working_hours_per_week"),
		monthly_wage=_coerce_int(profile.get("monthly_wage"), "monthly_wage"),
		pay_day=_coerce_int(profile.get("pay_day"), "pay_day"),
		probation_months=_coerce_int(profile.get("probation_months", 0), "probation_months"),
		work_location=profile.get("work_location"),
		work_duties=profile.get("work_duties"),
	)
	return {
		"contract_type": "korea_employment_contract_preview_v1",
		"runtime_action": "preview_only",
		"requires_runtime_apply": False,
		"contract_snapshot": deepcopy(contract_snapshot),
	}


def _coerce_mapping(value: Any, fieldname: str) -> dict[str, Any]:
	coerced = _coerce_json_if_needed(value)
	if not isinstance(coerced, dict):
		raise ValueError(f"{fieldname} must be a dict or JSON object")
	return dict(coerced)


def _coerce_json_if_needed(value: Any) -> Any:
	if isinstance(value, str):
		text = value.strip()
		if text.startswith("{") or text.startswith("["):
			try:
				return json.loads(text)
			except json.JSONDecodeError as exc:
				raise ValueError("JSON payload is invalid") from exc
	return value


def _coerce_date(value: Any, fieldname: str) -> dt.date:
	if type(value) is dt.date:
		return value
	if isinstance(value, str):
		try:
			return dt.date.fromisoformat(value.strip())
		except ValueError as exc:
			raise ValueError(f"{fieldname} must be an ISO date") from exc
	raise ValueError(f"{fieldname} must be an ISO date")


def _coerce_optional_date(value: Any, fieldname: str) -> dt.date | None:
	if value in (None, ""):
		return None
	return _coerce_date(value, fieldname)


def _coerce_int(value: Any, fieldname: str) -> int:
	if isinstance(value, bool) or (type(value) is not int and not isinstance(value, str)):
		raise ValueError(f"{fieldname} must be an integer")
	try:
		if isinstance(value, str):
			text = value.strip()
			if not text:
				raise ValueError
			if "." in text:
				raise ValueError
			return int(text)
		if type(value) is int:
			return value
	except ValueError as exc:
		raise ValueError(f"{fieldname} must be an integer") from exc
	raise ValueError(f"{fieldname} must be an integer")


def _coerce_float(value: Any, fieldname: str) -> float:
	if isinstance(value, bool):
		raise ValueError(f"{fieldname} must be numeric")
	try:
		return float(value)
	except (TypeError, ValueError) as exc:
		raise ValueError(f"{fieldname} must be numeric") from exc


def _load_sibling_module(filename: str, module_name: str):
	path = Path(__file__).with_name(filename)
	spec = importlib.util.spec_from_file_location(module_name, path)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


__all__ = ["preview_korea_employment_contract_snapshot"]
