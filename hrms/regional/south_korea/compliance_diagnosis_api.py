"""Frappe-facing preview API for Korea compliance diagnosis contracts.

This module is preview-only: it accepts checklist-shaped rows or period inputs,
returns the framework-free diagnosis contract, and never saves, submits, or
mutates Frappe documents. Direct file tests run without a bench; when Frappe is
present the function is whitelisted.
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
def preview_korea_compliance_diagnosis(
	*,
	items: Any | None = None,
	period_start: Any | None = None,
	period_end: Any | None = None,
	completed_codes: Any | None = None,
	today: Any | None = None,
	evidence: Any | None = None,
	reviewer: str = "HR Compliance Review Queue",
) -> dict[str, Any]:
	"""Return a side-effect-free Korea compliance diagnosis preview."""

	core = _load_sibling_module("compliance_checklist.py", "korea_compliance_checklist")
	checklist_items, source = _resolve_checklist_items(
		core,
		items=items,
		period_start=period_start,
		period_end=period_end,
		completed_codes=completed_codes,
		today=today,
	)
	try:
		diagnosis = core.build_compliance_diagnosis(
			deepcopy(checklist_items),
			evidence=_coerce_optional_mapping(evidence, "evidence") or {},
			reviewer=reviewer,
		)
	except TypeError as exc:
		raise ValueError(str(exc)) from exc
	return {
		"contract_type": "korea_compliance_diagnosis_preview_v1",
		"runtime_action": "preview_only",
		"requires_runtime_apply": True,
		"source": source,
		"diagnosis": deepcopy(diagnosis),
	}


def _resolve_checklist_items(
	core,
	*,
	items: Any | None,
	period_start: Any | None,
	period_end: Any | None,
	completed_codes: Any | None,
	today: Any | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
	has_items = items not in (None, "")
	has_period = period_start not in (None, "") or period_end not in (None, "")
	if has_items and has_period:
		raise ValueError("provide either items or period_start/period_end, not both")
	if not has_items and not has_period:
		raise ValueError("items or period_start/period_end is required")
	if has_period and (period_start in (None, "") or period_end in (None, "")):
		raise ValueError("period_start and period_end are both required")
	if has_items:
		resolved_items = _resolve_items(items)
		return resolved_items, {"input": "items"}

	start = _parse_iso_date(period_start, "period_start")
	end = _parse_iso_date(period_end, "period_end")
	checks = core.build_compliance_checklist(period_start=start, period_end=end)
	evaluated = core.evaluate_compliance_checklist(
		checks,
		completed_codes=set(_coerce_text_list(completed_codes, "completed_codes")),
		today=_parse_iso_date(today, "today") if today not in (None, "") else None,
	)
	return evaluated, {"input": "period", "period_start": start.isoformat(), "period_end": end.isoformat()}


def _resolve_items(value: Any) -> list[dict[str, Any]]:
	coerced = _coerce_json_if_needed(value)
	if isinstance(coerced, list):
		if not all(isinstance(item, dict) for item in coerced):
			raise ValueError("items must be a list of objects")
		return deepcopy(coerced)
	if isinstance(coerced, str) and coerced.strip():
		if frappe is None:
			raise RuntimeError("Frappe runtime is required to load compliance checklist items by name")
		doc = frappe.get_doc("Korea Compliance Checklist", coerced.strip())  # type: ignore[union-attr]
		return [row.as_dict() for row in getattr(doc, "items", [])]
	raise ValueError("items must be a list or JSON array")


def _coerce_optional_mapping(value: Any, fieldname: str) -> dict[str, Any] | None:
	if value in (None, ""):
		return None
	coerced = _coerce_json_if_needed(value)
	if not isinstance(coerced, dict):
		raise ValueError(f"{fieldname} must be a dict or JSON object")
	return coerced


def _coerce_text_list(value: Any, fieldname: str) -> list[str]:
	if value in (None, ""):
		return []
	coerced = _coerce_json_if_needed(value)
	if not isinstance(coerced, list):
		raise ValueError(f"{fieldname} must be a list")
	values: list[str] = []
	for entry in coerced:
		if not isinstance(entry, str):
			raise ValueError(f"{fieldname} entries must be strings")
		text = entry.strip()
		if not text:
			raise ValueError(f"{fieldname} entries must be non-empty")
		values.append(text)
	return values


def _parse_iso_date(value: Any, fieldname: str) -> dt.date:
	try:
		if isinstance(value, dt.datetime):
			return value.date()
		if isinstance(value, dt.date):
			return value
		return dt.date.fromisoformat(str(value or "").strip())
	except ValueError as exc:
		raise ValueError(f"{fieldname} must be an ISO date") from exc


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


__all__ = ["preview_korea_compliance_diagnosis"]
