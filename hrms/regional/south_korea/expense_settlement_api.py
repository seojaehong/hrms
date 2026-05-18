"""Frappe-facing preview API for Korea expense settlement contracts.

This module is intentionally preview-only: it normalizes caller-supplied Expense
Claim-shaped rows and returns settlement/reimbursement contracts without saving,
submitting, paying, or mutating documents. Direct file tests can run without a
bench; when Frappe is present the function is whitelisted.
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
def preview_korea_expense_settlement(*, claims: Any) -> dict[str, Any]:
	"""Return a side-effect-free Korea expense settlement preview."""

	coerced_claims = _coerce_claims(claims)
	expense_settlement = _load_sibling_module("expense_settlement.py", "korea_expense_settlement")
	settlement = expense_settlement.build_cost_settlement(claims=coerced_claims)
	reimbursement_batch = expense_settlement.build_reimbursement_batch(coerced_claims)
	return {
		"contract_type": "korea_expense_settlement_preview_v1",
		"runtime_action": "preview_only",
		"requires_runtime_apply": False,
		"claims": deepcopy(coerced_claims),
		"settlement": deepcopy(settlement),
		"reimbursement_batch": deepcopy(reimbursement_batch),
	}


def _coerce_claims(value: Any) -> list[dict[str, Any]]:
	coerced = _coerce_json_if_needed(value)
	if not isinstance(coerced, list):
		raise ValueError("claims must be a list or JSON array")
	claims: list[dict[str, Any]] = []
	for index, item in enumerate(coerced):
		if not isinstance(item, dict):
			raise ValueError(f"claims[{index}] must be a dict")
		claims.append(deepcopy(item))
	return claims


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


__all__ = ["preview_korea_expense_settlement"]
