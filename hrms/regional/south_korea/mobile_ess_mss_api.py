"""Frappe-facing preview API for Korea mobile ESS/MSS contracts.

This module is intentionally preview-only: it shapes employee self-service and
manager self-service mobile payloads without saving, submitting, or mutating
Frappe documents. Direct file tests run without a bench; inside Frappe the
functions are whitelisted.
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
def preview_korea_mobile_employee_home(*, employee: str, period: Any, records: Any) -> dict[str, Any]:
	"""Return a side-effect-free employee mobile home preview."""

	mobile = _load_sibling_module("mobile_ess_mss.py", "korea_mobile_ess_mss")
	home = mobile.build_mobile_employee_home(
		employee=employee,
		period=_coerce_mapping(period, "period"),
		records=_coerce_list(records, "records"),
	)
	return {
		"contract_type": "korea_mobile_ess_home_preview_v1",
		"runtime_action": "preview_only",
		"requires_runtime_apply": False,
		"home": deepcopy(home),
	}


@_whitelist
def preview_korea_mobile_manager_worklist(
	*,
	manager: str,
	period: Any,
	records: Any,
	workplace: str | None = None,
	today: Any | None = None,
	overdue_after_days: int = 3,
) -> dict[str, Any]:
	"""Return a side-effect-free manager mobile worklist preview."""

	mobile = _load_sibling_module("mobile_ess_mss.py", "korea_mobile_ess_mss")
	worklist = mobile.build_mobile_manager_worklist(
		manager=manager,
		period=_coerce_mapping(period, "period"),
		workplace=workplace,
		records=_coerce_list(records, "records"),
		today=_coerce_optional_date(today, "today"),
		overdue_after_days=_coerce_int(overdue_after_days, "overdue_after_days"),
	)
	return {
		"contract_type": "korea_mobile_mss_worklist_preview_v1",
		"runtime_action": "preview_only",
		"requires_runtime_apply": False,
		"worklist": deepcopy(worklist),
	}


def _coerce_list(value: Any, fieldname: str) -> list[dict[str, Any]]:
	coerced = _coerce_json_if_needed(value)
	if not isinstance(coerced, list):
		raise ValueError(f"{fieldname} must be a list or JSON array")
	if not all(isinstance(item, dict) for item in coerced):
		raise ValueError(f"{fieldname} entries must be dict objects")
	return deepcopy(coerced)


def _coerce_mapping(value: Any, fieldname: str) -> dict[str, Any]:
	coerced = _coerce_json_if_needed(value)
	if not isinstance(coerced, dict):
		raise ValueError(f"{fieldname} must be a dict or JSON object")
	return deepcopy(coerced)


def _coerce_optional_date(value: Any, fieldname: str) -> dt.date | None:
	if value in (None, ""):
		return None
	if isinstance(value, dt.datetime):
		return value.date()
	if isinstance(value, dt.date):
		return value
	if isinstance(value, str):
		try:
			return dt.date.fromisoformat(value.strip())
		except ValueError as exc:
			raise ValueError(f"{fieldname} must be an ISO date string") from exc
	raise ValueError(f"{fieldname} must be a date or ISO date string")


def _coerce_int(value: Any, fieldname: str) -> int:
	if isinstance(value, bool):
		raise ValueError(f"{fieldname} must be an integer")
	if isinstance(value, int):
		return value
	if isinstance(value, str):
		text = value.strip()
		if text and text.isdecimal():
			return int(text)
	raise ValueError(f"{fieldname} must be an integer")


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
	"preview_korea_mobile_employee_home",
	"preview_korea_mobile_manager_worklist",
]
