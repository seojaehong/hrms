"""Frappe-facing runtime API for Korea payroll closing review audit-log inserts.

This wrapper accepts only the core audit-log preview contract and delegates to the
Korea Payroll Closing Review Audit Log DocType controller. It inserts only the
audit row and does not submit payroll, approve payroll, send notifications, call
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
def create_korea_payroll_closing_review_audit_log_runtime(
	*,
	audit_log: Any,
	audit_actor: Any | None = None,
) -> dict[str, Any]:
	"""Persist a guarded payroll closing draft-review audit log row."""

	audit_log_payload = deepcopy(_coerce_mapping(audit_log, "audit_log"))
	audit_actor_text = _resolve_actor(audit_actor)
	_enforce_runtime_create_access()
	controller = _load_doctype_controller()
	result = deepcopy(
		controller.create_korea_payroll_closing_review_audit_log(
			audit_log_payload,
			audit_actor=audit_actor_text,
		)
	)
	runtime_insert_contract_type = result.get("contract_type")
	result.update(
		{
			"contract_type": "korea_payroll_closing_review_audit_log_runtime_insert_api_v1",
			"runtime_insert_contract_type": runtime_insert_contract_type,
			"runtime_action": "runtime_review_audit_log_created",
			"requires_runtime_apply": False,
			"mutation_boundary": "audit_log_only_no_submit_no_send_no_provider_call",
			"requires_human_approval": True,
			"ai_role": "assistant_only",
		}
	)
	return result


def _resolve_actor(audit_actor: Any | None) -> str:
	if frappe is None or not getattr(frappe, "session", None):
		if audit_actor is None:
			raise ValueError("audit_actor is required outside a Frappe session")
		if not isinstance(audit_actor, str) or not audit_actor.strip():
			raise ValueError("audit_actor must be a non-empty string")
		return audit_actor.strip()
	session_user = getattr(frappe.session, "user", None)
	if not isinstance(session_user, str) or not session_user.strip():
		raise ValueError("authenticated session user is required")
	session_actor = session_user.strip()
	if audit_actor is not None:
		if not isinstance(audit_actor, str) or not audit_actor.strip():
			raise ValueError("audit_actor must be a non-empty string")
		if audit_actor.strip() != session_actor:
			raise ValueError("audit_actor must match the authenticated session user")
	return session_actor


def _enforce_runtime_create_access() -> None:
	if frappe is None:
		return
	frappe.only_for(["HR Manager"])  # type: ignore[union-attr]
	if not frappe.has_permission("Korea Payroll Closing Review Audit Log", ptype="create"):  # type: ignore[union-attr]
		raise PermissionError("create permission is required for Korea Payroll Closing Review Audit Log")


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
	path = (
		Path(__file__).resolve().parents[2]
		/ "hr"
		/ "doctype"
		/ "korea_payroll_closing_review_audit_log"
		/ "korea_payroll_closing_review_audit_log.py"
	)
	spec = importlib.util.spec_from_file_location("korea_payroll_closing_review_audit_log_runtime_doctype", path)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	stubbed_names: list[str] = []
	previous_modules: dict[str, Any] = {}

	def install_stub(name: str, value: Any) -> None:
		previous_modules[name] = sys.modules.get(name)
		sys.modules[name] = value
		stubbed_names.append(name)

	if frappe is not None and "frappe" not in sys.modules:
		install_stub("frappe", frappe)
	if frappe is not None and "frappe.model.document" not in sys.modules:
		if "frappe.model" not in sys.modules:
			install_stub("frappe.model", types.ModuleType("frappe.model"))
		document = types.ModuleType("frappe.model.document")

		class Document:  # direct-run no-bench stub only
			pass

		document.Document = Document
		install_stub("frappe.model.document", document)
	try:
		spec.loader.exec_module(module)
	finally:
		for name in reversed(stubbed_names):
			previous = previous_modules[name]
			if previous is None:
				sys.modules.pop(name, None)
			else:
				sys.modules[name] = previous
	return module


__all__ = ["create_korea_payroll_closing_review_audit_log_runtime"]
