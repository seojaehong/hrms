"""Frappe-facing preview API for Korea payroll closing draft apply plans.

This wrapper accepts a validated core ``korea_payroll_closing_draft_v1`` payload
as a dict or JSON object, delegates to the framework-free apply-plan helper via
file-path import for no-bench execution, and returns a preview-only API contract.
It does not save, submit, approve, send, call providers, or mutate runtime docs.
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
def preview_korea_payroll_closing_draft_apply_plan(*, draft: Any, actor: Any) -> dict[str, Any]:
	"""Return a side-effect-free preview of a runtime draft apply plan."""

	draft_payload = deepcopy(_coerce_mapping(draft, "draft"))
	core = _load_sibling_module("payroll_closing_draft_apply.py", "korea_payroll_closing_draft_apply")
	plan = deepcopy(core.build_korea_payroll_closing_draft_apply_plan(draft_payload, actor=actor))
	apply_plan_contract_type = plan.get("contract_type")
	plan.update(
		{
			"contract_type": "korea_payroll_closing_draft_apply_plan_preview_v1",
			"apply_plan_contract_type": apply_plan_contract_type,
			"runtime_action": "preview_only",
			"requires_runtime_apply": True,
		}
	)
	return plan


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


__all__ = ["preview_korea_payroll_closing_draft_apply_plan"]
