"""Frappe-facing preview API for Korea approval inbox/action contracts.

This module is intentionally preview-only: it normalizes approval inbox records
and builds approve/reject action contracts without saving, submitting, or
mutating Frappe documents. Direct file tests can run without a bench; when
Frappe is present the functions are whitelisted.
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
def preview_korea_approval_inbox(
	*,
	records: Any,
	actor: str,
	today: Any | None = None,
	overdue_after_days: int = 3,
) -> dict[str, Any]:
	"""Return a side-effect-free unified approval inbox preview."""

	approval = _load_sibling_module("approval_inbox.py", "korea_approval_inbox")
	items = approval.build_approval_inbox(
		_coerce_list(records, "records"),
		actor=actor,
		today=_coerce_optional_date(today, "today"),
		overdue_after_days=_coerce_integer(overdue_after_days, "overdue_after_days"),
	)
	return {
		"contract_type": "korea_approval_inbox_preview_v1",
		"runtime_action": "preview_only",
		"requires_runtime_apply": False,
		"actor": actor,
		"items": deepcopy(items),
		"summary": approval.summarize_inbox(items),
	}


@_whitelist
def preview_korea_approval_action(*, item: Any, action: str, actor: str, note: str | None = None) -> dict[str, Any]:
	"""Return a side-effect-free single approval action preview."""

	approval = _load_sibling_module("approval_inbox.py", "korea_approval_inbox")
	payload = approval.build_approval_action(
		_coerce_mapping(item, "item"),
		action=action,
		actor=actor,
		note=note,
	)
	payload = deepcopy(payload)
	payload.update(
		{
			"contract_type": "korea_approval_action_preview_v1",
			"runtime_action": "preview_only",
		}
	)
	return payload


@_whitelist
def preview_korea_approval_batch_action(
	*,
	items: Any,
	action: str,
	actor: str,
	note: str | None = None,
) -> dict[str, Any]:
	"""Return a side-effect-free batch approval action preview."""

	approval = _load_sibling_module("approval_inbox.py", "korea_approval_inbox")
	payload = approval.build_approval_batch_action(
		_coerce_list(items, "items"),
		action=action,
		actor=actor,
		note=note,
	)
	payload = deepcopy(payload)
	payload.update(
		{
			"contract_type": "korea_approval_batch_action_preview_v1",
			"runtime_action": "preview_only",
		}
	)
	return payload


def _coerce_list(value: Any, fieldname: str) -> list[dict[str, Any]]:
	coerced = _coerce_json_if_needed(value)
	if not isinstance(coerced, list):
		raise ValueError(f"{fieldname} must be a list or JSON array")
	if not all(isinstance(item, dict) for item in coerced):
		raise ValueError(f"{fieldname} entries must be dict objects")
	return coerced


def _coerce_mapping(value: Any, fieldname: str) -> dict[str, Any]:
	coerced = _coerce_json_if_needed(value)
	if not isinstance(coerced, dict):
		raise ValueError(f"{fieldname} must be a dict or JSON object")
	return coerced


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


def _coerce_integer(value: Any, fieldname: str) -> int:
	if isinstance(value, bool):
		raise ValueError(f"{fieldname} must be an integer")
	if isinstance(value, int):
		return value
	if isinstance(value, float):
		if not value.is_integer():
			raise ValueError(f"{fieldname} must be an integer")
		return int(value)
	if isinstance(value, str):
		text = value.strip()
		if not text or any(ch not in "0123456789+-" for ch in text) or text in {"+", "-"}:
			raise ValueError(f"{fieldname} must be an integer")
		try:
			return int(text)
		except ValueError as exc:
			raise ValueError(f"{fieldname} must be an integer") from exc
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
	"preview_korea_approval_inbox",
	"preview_korea_approval_action",
	"preview_korea_approval_batch_action",
]
