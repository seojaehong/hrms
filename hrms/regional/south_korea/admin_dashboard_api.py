"""Frappe-facing preview API for Korea admin dashboard contracts.

This module is intentionally preview-only: it normalizes caller-supplied metrics
and returns route/action card contracts without saving, mutating documents, or
performing runtime lookups. Direct file tests can run without a bench; when
Frappe is present the function is whitelisted.
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
def preview_korea_admin_dashboard(*, metrics: Any) -> dict[str, Any]:
	"""Return a side-effect-free Korea admin home dashboard preview."""

	coerced_metrics = _coerce_mapping(metrics, "metrics")
	admin_dashboard = _load_sibling_module("admin_dashboard.py", "korea_admin_dashboard")
	dashboard = admin_dashboard.build_admin_dashboard(metrics=coerced_metrics)
	return {
		"contract_type": "korea_admin_dashboard_preview_v1",
		"runtime_action": "preview_only",
		"requires_runtime_apply": False,
		"dashboard": deepcopy(dashboard),
	}


def _coerce_mapping(value: Any, fieldname: str) -> dict[str, Any]:
	coerced = _coerce_json_if_needed(value)
	if not isinstance(coerced, dict):
		raise ValueError(f"{fieldname} must be a dict or JSON object")
	return deepcopy(coerced)


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


__all__ = ["preview_korea_admin_dashboard"]
