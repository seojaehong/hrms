"""Frappe-facing preview API for Korea payroll closing draft review audit logs.

This wrapper exposes the framework-free audit-log preview contract to Desk/UI
callers without persisting an audit row. It accepts only dict/JSON runtime review
apply payloads, delegates to ``payroll_closing_draft_review_audit_log.py`` by
file-path import for no-bench execution, and never saves, submits, approves,
sends, calls providers, or creates payroll documents.
"""

from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

try:  # pragma: no cover - exercised only inside a Frappe bench or test stub
	import frappe  # type: ignore
except ImportError:  # pragma: no cover - direct-run no-bench import mode
	frappe = None  # type: ignore


def _whitelist(fn):
	if frappe is None:
		return fn
	return frappe.whitelist()(fn)


@_whitelist
def preview_korea_payroll_closing_draft_review_audit_log(*, runtime_apply: Any, audit_actor: Any) -> dict[str, Any]:
	"""Return a side-effect-free preview of a draft review audit-log row.

	The wrapper JSON-coerces only the API boundary input, defensive-copies caller
	payloads and outputs, and preserves human-approval / assistant-only metadata
	from the core audit-log contract.
	"""

	runtime_apply_payload = deepcopy(_coerce_mapping(runtime_apply, "runtime_apply"))
	audit_actor_text = _require_text(audit_actor, "audit_actor")
	core = _load_sibling_module(
		"payroll_closing_draft_review_audit_log.py",
		"korea_payroll_closing_draft_review_audit_log",
	)
	result = deepcopy(
		core.build_korea_payroll_closing_draft_review_audit_log(
			runtime_apply_payload,
			audit_actor=audit_actor_text,
		)
	)
	audit_log_contract_type = result.get("contract_type")
	result.update(
		{
			"contract_type": "korea_payroll_closing_draft_review_audit_log_preview_v1",
			"audit_log_contract_type": audit_log_contract_type,
			"runtime_action": "preview_only",
			"requires_runtime_apply": True,
			"requires_human_approval": True,
			"ai_role": "assistant_only",
		}
	)
	return result


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


def _require_text(value: Any, label: str) -> str:
	if not isinstance(value, str) or not value.strip():
		raise ValueError(f"{label} must be a non-empty string")
	return value.strip()


def _load_sibling_module(filename: str, module_name: str):
	path = Path(__file__).resolve().with_name(filename)
	spec = importlib.util.spec_from_file_location(module_name, path)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


__all__ = ["preview_korea_payroll_closing_draft_review_audit_log"]
