"""Frappe-facing preview API for Korea Closing Center contracts.

This module is intentionally preview-only: it shapes workplace-scoped monthly
closing center payloads without saving, submitting, or mutating Frappe documents.
Direct file tests run without a bench; inside Frappe the function is whitelisted.
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
def preview_korea_closing_center(*, workplace: str, period: Any, items: Any) -> dict[str, Any]:
	"""Return a side-effect-free Korea monthly closing center preview."""

	closing = _load_sibling_module("closing_center.py", "korea_closing_center")
	center = closing.build_closing_center(
		workplace=workplace,
		period=_coerce_mapping(period, "period"),
		items=_coerce_list(items, "items"),
	)
	return {
		"contract_type": "korea_closing_center_preview_v1",
		"runtime_action": "preview_only",
		"requires_runtime_apply": False,
		"center": deepcopy(center),
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


__all__ = ["preview_korea_closing_center"]
