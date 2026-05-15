"""Frappe-facing runtime API for Korea payroll closing draft review status updates.

This wrapper accepts only the core framework-free review action contract and
applies the narrow runtime status update via the Korea Payroll Closing Draft
DocType controller. It does not submit, approve payroll, send notifications, call
providers, or create payroll documents.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import types
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
def apply_korea_payroll_closing_draft_review_runtime(
	*,
	review_action: Any,
	actor: Any | None = None,
) -> dict[str, Any]:
	"""Apply a guarded human-review status update to a runtime draft row."""

	review_action_payload = deepcopy(_coerce_mapping(review_action, "review_action"))
	actor_text = _resolve_actor(actor)
	_enforce_runtime_write_access()
	controller = _load_doctype_controller()
	result = deepcopy(
		controller.apply_korea_payroll_closing_draft_review_action(
			review_action_payload,
			actor=actor_text,
		)
	)
	runtime_apply_contract_type = result.get("contract_type")
	result.update(
		{
			"contract_type": "korea_payroll_closing_draft_review_runtime_apply_api_v1",
			"runtime_apply_contract_type": runtime_apply_contract_type,
			"runtime_action": "runtime_draft_review_status_updated",
			"requires_runtime_apply": False,
			"mutation_boundary": "human_review_status_only_no_submit_no_send_no_provider_call",
			"requires_human_approval": True,
			"ai_role": "assistant_only",
		}
	)
	return result


def _resolve_actor(actor: Any | None) -> str:
	if frappe is None or not getattr(frappe, "session", None):
		if actor is None:
			raise ValueError("actor is required outside a Frappe session")
		if not isinstance(actor, str) or not actor.strip():
			raise ValueError("actor must be a non-empty string")
		return actor.strip()
	session_user = getattr(frappe.session, "user", None)
	if not isinstance(session_user, str) or not session_user.strip():
		raise ValueError("authenticated session user is required")
	session_actor = session_user.strip()
	if actor is not None:
		if not isinstance(actor, str) or not actor.strip():
			raise ValueError("actor must be a non-empty string")
		if actor.strip() != session_actor:
			raise ValueError("actor must match the authenticated session user")
	return session_actor


def _enforce_runtime_write_access() -> None:
	if frappe is None:
		return
	frappe.only_for(["HR Manager"])  # type: ignore[union-attr]
	if not frappe.has_permission("Korea Payroll Closing Draft", ptype="write"):  # type: ignore[union-attr]
		raise PermissionError("write permission is required for Korea Payroll Closing Draft")


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


def _load_doctype_controller():
	path = Path(__file__).resolve().parents[2] / "hr" / "doctype" / "korea_payroll_closing_draft" / "korea_payroll_closing_draft.py"
	spec = importlib.util.spec_from_file_location("korea_payroll_closing_draft_review_runtime_doctype", path)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	installed_stub_names: list[str] = []
	if frappe is not None and "frappe" not in sys.modules:
		sys.modules["frappe"] = frappe
		installed_stub_names.append("frappe")
	if frappe is not None and "frappe.model.document" not in sys.modules:
		model = types.ModuleType("frappe.model")
		document = types.ModuleType("frappe.model.document")
		class Document:  # direct-run no-bench stub only
			pass
		document.Document = Document
		sys.modules["frappe.model"] = model
		sys.modules["frappe.model.document"] = document
		installed_stub_names.extend(["frappe.model", "frappe.model.document"])
	try:
		spec.loader.exec_module(module)
	finally:
		for name in reversed(installed_stub_names):
			sys.modules.pop(name, None)
	return module


__all__ = ["apply_korea_payroll_closing_draft_review_runtime"]
